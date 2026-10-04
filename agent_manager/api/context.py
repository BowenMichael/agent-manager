import logging
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from agent_manager.runner import AgentRunnerManager
from agent_manager.utils.git import get_git_tree
from agent_manager.github import get_issue, get_issue_comments

logger = logging.getLogger("agent_manager.api.context")

router = APIRouter(prefix="/api/agents", tags=["context"])


class GitTreeResponse(BaseModel):
    session_id: str
    branch: Optional[str] = None
    worktree_path: Optional[str] = None
    git_tree: str


class IssueContextResponse(BaseModel):
    session_id: str
    repo: str
    issue_number: Optional[int] = None
    issue: Optional[Dict[str, Any]] = None
    comments: List[Dict[str, Any]] = []


@router.get("/{session_id}/git-tree", response_model=GitTreeResponse)
async def get_agent_git_tree(session_id: str):
    """Returns the git tree topology / log for the agent session worktree."""
    runner = AgentRunnerManager()
    session = runner.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent session '{session_id}' not found."
        )

    worktree_path = session.worktree_path
    if not worktree_path:
        return GitTreeResponse(
            session_id=session_id,
            branch=session.git_branch,
            worktree_path=None,
            git_tree="No worktree path associated with this session."
        )

    tree_output = await get_git_tree(worktree_path)
    return GitTreeResponse(
        session_id=session_id,
        branch=session.git_branch,
        worktree_path=worktree_path,
        git_tree=tree_output
    )


@router.get("/{session_id}/issue", response_model=IssueContextResponse)
async def get_agent_issue_context(session_id: str):
    """Returns GitHub issue information and conversation stream for the session."""
    runner = AgentRunnerManager()
    session = runner.get_session(session_id)
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent session '{session_id}' not found."
        )

    repo = session.repo
    issue_num = session.issue_number

    if not repo or not issue_num:
        return IssueContextResponse(
            session_id=session_id,
            repo=repo or "Unknown",
            issue_number=issue_num,
            issue=None,
            comments=[]
        )

    issue_data = await get_issue(repo, issue_num)
    comments_data = await get_issue_comments(repo, issue_num)

    return IssueContextResponse(
        session_id=session_id,
        repo=repo,
        issue_number=issue_num,
        issue=issue_data,
        comments=comments_data
    )
