import logging
from typing import Dict, Any, List, Set, Tuple

logger = logging.getLogger("agent_manager.cron.evaluator")


def inspect_active_local_agents() -> Tuple[List[str], Set[str], List[str]]:
    """
    Inspects running or initializing agent sessions locally.
    In Review agents DO NOT count as running agents.
    Returns:
        (active_local_agents, active_local_issue_keys, in_review_agents)
    """
    active_local_agents: List[str] = []
    active_local_issue_keys: Set[str] = set()
    in_review_agents: List[str] = []

    try:
        from agent_manager.runner import AgentRunnerManager
        from agent_manager.models import AgentStatus

        runner = AgentRunnerManager()
        for s in runner.list_sessions(include_archived=False):
            # In Review agents do NOT count as running agents
            if s.status in (AgentStatus.RUNNING, AgentStatus.INITIALIZING):
                active_local_agents.append(s.session_id)
                if s.repo and s.issue_number:
                    active_local_issue_keys.add(f"{s.repo}#{s.issue_number}".lower())
                    active_local_issue_keys.add(str(s.issue_number))
            elif s.status == AgentStatus.IN_REVIEW:
                in_review_agents.append(s.session_id)

        if getattr(runner, "_active_agents", None):
            for sid, proc in runner._active_agents.items():
                if proc and getattr(proc, "returncode", None) is None:
                    sess = runner.get_session(sid)
                    # Exclude IN_REVIEW, PAUSED, STOPPED, COMPLETED sessions
                    if sess and sess.status in (AgentStatus.IN_REVIEW, AgentStatus.PAUSED, AgentStatus.STOPPED, AgentStatus.COMPLETED):
                        if sess.status == AgentStatus.IN_REVIEW and sid not in in_review_agents:
                            in_review_agents.append(sid)
                        continue
                    if sid not in active_local_agents:
                        active_local_agents.append(sid)
    except Exception as e:
        logger.warning(f"[Cron Dispatcher] Could not inspect local agent sessions: {e}")

    if in_review_agents:
        logger.info(
            f"[Cron Dispatcher] Observed {len(in_review_agents)} local agent(s) in review "
            f"({in_review_agents}) - not counted as running agents."
        )

    return active_local_agents, active_local_issue_keys, in_review_agents


async def evaluate_and_dispatch_projects(
    boards_data: Dict[str, Dict[str, Any]],
    active_local_issue_keys: Set[str],
    watcher: Any,
    promote_fn: Any
) -> Dict[str, Any]:
    """
    Evaluates each project board independently.
    Promotes one backlog item for each idle project.
    """
    project_results: Dict[str, Dict[str, Any]] = {}
    promoted_count = 0
    active_projects_count = 0
    promoted_items = []

    for pid, pdata in boards_data.items():
        board_title = pdata.get("board_title", pid)
        active_items = pdata.get("active_items", [])
        in_review_items = pdata.get("in_review_items", [])
        backlog_items = pdata.get("backlog_items", [])

        if in_review_items:
            rev_desc = [f"#{x.get('issue_number')}" for x in in_review_items]
            logger.info(
                f"[Cron Dispatcher] Observed {len(in_review_items)} item(s) in review for [{board_title}] "
                f"({', '.join(rev_desc)}) - not counted as running agents."
            )

        # Check if any board items match running local agents
        local_active_for_project = []
        for item in active_items + backlog_items:
            item_repo = item.get("repo")
            item_num = item.get("issue_number")
            key = f"{item_repo}#{item_num}".lower() if item_repo and item_num else None
            num_key = str(item_num) if item_num else None
            if (key and key in active_local_issue_keys) or (num_key and num_key in active_local_issue_keys):
                local_active_for_project.append(f"#{item_num}")

        if active_items or local_active_for_project:
            active_projects_count += 1
            active_desc = [f"#{x.get('issue_number')} ({x.get('status')})" for x in active_items]
            if local_active_for_project:
                active_desc.extend([f"{x} (Local Agent Running)" for x in set(local_active_for_project)])
            msg = f"Active task(s) detected in [{board_title}]: {', '.join(active_desc)}. Skipping backlog promotion."
            logger.info(f"[Cron Dispatcher] {msg}")
            project_results[pid] = {
                "status": "active_issue_present",
                "board_title": board_title,
                "message": msg,
                "active_count": len(active_items) + len(local_active_for_project),
                "active_items": active_items,
                "in_review_count": len(in_review_items),
                "in_review_items": in_review_items,
                "backlog_count": len(backlog_items)
            }
            continue

        if not backlog_items:
            msg = f"No backlog items found for [{board_title}]. Nothing to dispatch."
            logger.info(f"[Cron Dispatcher] {msg}")
            project_results[pid] = {
                "status": "backlog_empty",
                "board_title": board_title,
                "message": msg,
                "active_count": 0,
                "in_review_count": len(in_review_items),
                "in_review_items": in_review_items,
                "backlog_count": 0
            }
            continue

        chosen = backlog_items[0]
        success, msg = await promote_fn(watcher, chosen)
        if success:
            promoted_count += 1
            promoted_items.append(chosen)
            project_results[pid] = {
                "status": "dispatched",
                "board_title": board_title,
                "message": msg,
                "promoted_issue": chosen,
                "in_review_count": len(in_review_items),
                "remaining_backlog_count": len(backlog_items) - 1
            }
        else:
            project_results[pid] = {
                "status": "error",
                "board_title": board_title,
                "message": msg,
                "attempted_issue": chosen,
                "in_review_count": len(in_review_items)
            }

    # Aggregate status
    if promoted_count > 0:
        overall_status = "dispatched"
        overall_msg = f"Promoted {promoted_count} issue(s) across connected project(s)."
    elif active_projects_count == len(boards_data) and boards_data:
        overall_status = "active_issue_present"
        overall_msg = "All connected project(s) have active tasks in progress."
    else:
        overall_status = "idle"
        overall_msg = "Evaluated connected project(s); no promotions needed or backlogs empty."

    first_promoted = promoted_items[0] if promoted_items else None
    return {
        "status": overall_status,
        "message": overall_msg,
        "promoted_count": promoted_count,
        "projects": project_results,
        "promoted_issue": first_promoted,
    }
