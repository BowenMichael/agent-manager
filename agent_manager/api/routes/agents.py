import subprocess
from fastapi import APIRouter, HTTPException
from agent_manager.models import (
    SpawnRequest, AddContextRequest, StopAgentRequest, AgentSessionInfo
)
from agent_manager.runner import AgentRunnerManager
from agent_manager.poller import LocalGitWatcher
import agent_manager.config as config

router = APIRouter(prefix="/api/agents", tags=["agents"])
runner = AgentRunnerManager()
watcher = LocalGitWatcher()


@router.get("", response_model=list[AgentSessionInfo])
async def list_agents(include_archived: bool = True):
    return runner.list_sessions(include_archived=include_archived)


@router.post("/{session_id}/archive")
async def archive_agent(session_id: str):
    success = await runner.archive_agent(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": f"Agent {session_id} archived"}


@router.post("/{session_id}/unarchive")
async def unarchive_agent(session_id: str):
    success = await runner.unarchive_agent(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": f"Agent {session_id} unarchived"}


@router.delete("/{session_id}")
async def delete_agent(session_id: str):
    success = await runner.delete_agent(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": f"Agent {session_id} deleted"}


@router.get("/{session_id}", response_model=AgentSessionInfo)
async def get_agent(session_id: str):
    session = runner.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return session


@router.post("/spawn", response_model=AgentSessionInfo)
async def spawn_agent(req: SpawnRequest):
    return await runner.spawn_agent(req)


@router.post("/{session_id}/launch-terminal")
async def launch_terminal(session_id: str):
    session = runner.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    cwd_dir = session.worktree_path or str(config.WORKSPACE_BASE)
    cmd = session.terminal_command or f'& "{config.AGY_CLI_PATH}" --dangerously-skip-permissions -i "Work on Issue #{session.issue_number}"'
    ps_cmd = f'powershell -NoExit -Command "$host.ui.RawUI.WindowTitle = \'Antigravity CLI (agy) - Issue #{session.issue_number}\'; {cmd}"'
    subprocess.Popen(f'start {ps_cmd}', cwd=str(cwd_dir), shell=True)
    return {"status": "ok", "message": "Terminal launched", "command": cmd}


@router.post("/{session_id}/resume")
async def resume_agent(session_id: str):
    success = await runner.resume_agent(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": "Agent resumed successfully"}


@router.post("/{session_id}/restart", response_model=AgentSessionInfo)
async def restart_agent(session_id: str):
    session = await runner.restart_agent(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return session


@router.post("/{session_id}/interrupt")
async def interrupt_agent(session_id: str):
    success = await runner.interrupt_agent(session_id)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": f"Agent {session_id} interrupted"}


@router.post("/{session_id}/complete")
async def complete_agent(session_id: str):
    session = runner.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")

    key = f"{session.repo}#{session.issue_number}"
    if session.issue_number and key in watcher.item_id_map:
        await watcher.update_item_status(watcher.item_id_map[key], "done")

    success = await runner.complete_agent(session_id, reason="Manually marked as Done by user")
    return {"status": "ok", "message": f"Agent {session_id} marked as Done and archived"}


@router.post("/{session_id}/compact")
async def compact_agent(session_id: str):
    session = runner.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Agent session not found")
    success = await runner.compact_session(session_id, force=True)
    return {"status": "ok", "message": f"Agent {session_id} chat compacted", "is_compacted": session.is_compacted}


@router.post("/{session_id}/stop")
async def stop_agent(session_id: str, req: StopAgentRequest = StopAgentRequest()):
    success = await runner.stop_agent(session_id, req.reason or "Stopped via UI")
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": f"Agent {session_id} stopped"}


@router.post("/{session_id}/context")
async def add_context(session_id: str, req: AddContextRequest):
    if not req.context.strip():
        raise HTTPException(status_code=400, detail="Context cannot be empty")
    success = await runner.add_context(session_id, req.context)
    if not success:
        raise HTTPException(status_code=404, detail="Agent session not found")
    return {"status": "ok", "message": "Context injected successfully"}
