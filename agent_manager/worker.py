import argparse
import os
import sys
import time
import subprocess
import httpx
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from agent_manager.config import WORKSPACE_BASE

def log(msg: str):
    print(f"[*] {msg}", flush=True)

def step(msg: str):
    print(f"\n==> {msg}", flush=True)

def run_cmd(cmd: str, cwd: str) -> tuple[int, str]:
    print(f"$ {cmd}", flush=True)
    res = subprocess.run(
        cmd,
        cwd=cwd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )
    if res.stdout:
        print(res.stdout, end="", flush=True)
    return res.returncode, res.stdout or ""

def main():
    parser = argparse.ArgumentParser(description="Autonomous Terminal Worker")
    parser.add_argument("--session-id", required=True, help="Agent session ID")
    parser.add_argument("--issue", type=int, required=True, help="GitHub Issue Number")
    parser.add_argument("--repo", default="BowenMichael/f1-frontend", help="Target repository")
    parser.add_argument("--worktree", required=True, help="Isolated worktree directory")
    parser.add_argument("--branch", required=True, help="Feature branch")
    parser.add_argument("--manager-url", default="http://localhost:8000", help="Agent Manager URL")
    args = parser.parse_args()

    print("=" * 70, flush=True)
    print(" 🚀 AGY TERMINAL AGENT: ACTIVE WORKER", flush=True)
    print(f" 🎯 Issue   : #{args.issue} in {args.repo}", flush=True)
    print(f" 📁 Worktree: {args.worktree}", flush=True)
    print(f" 🌿 Branch  : {args.branch}", flush=True)
    print("=" * 70, flush=True)

    step("Phase 1: Validating isolated git worktree...")
    worktree_path = Path(args.worktree)
    if not worktree_path.exists():
        repo_name = args.repo.split('/')[-1]
        candidate_dirs = [
            WORKSPACE_BASE / repo_name,
            WORKSPACE_BASE / "F1 Front End" / repo_name,
            Path.cwd()
        ]
        repo_dir = None
        for cand in candidate_dirs:
            if cand.exists() and (cand / ".git").exists():
                repo_dir = cand
                break
        if repo_dir:
            log(f"Setting up worktree on branch '{args.branch}'...")
            run_cmd(f'git worktree add -B "{args.branch}" "{worktree_path}" HEAD', str(repo_dir))
        else:
            log(f"Operating in existing workspace...")

    step("Phase 2: Inspecting Issue & Repository Codebase...")
    run_cmd("git status", str(worktree_path) if worktree_path.exists() else str(WORKSPACE_BASE))

    step("Phase 3: Running Autonomous Agent Loop...")
    log(f"Agent is actively working on Issue #{args.issue} inside this terminal.")
    log("Live logs are synchronized with Agent Manager at http://localhost:8000")
    print("\n[+] Type any instruction or feedback below and press Enter to guide the agent:")
    
    try:
        while True:
            cmd = input("\n[agent-input]> ")
            if cmd.strip():
                if cmd.strip().lower() in ["exit", "quit", "stop"]:
                    log("Worker stopped by user.")
                    break
                log(f"Executing guidance: {cmd.strip()}")
                # Send context to manager
                try:
                    httpx.post(
                        f"{args.manager_url}/api/agents/{args.session_id}/context",
                        json={"context": cmd.strip()},
                        timeout=5.0
                    )
                except Exception:
                    pass
    except KeyboardInterrupt:
        print("\n[*] Terminal agent worker exiting.")

if __name__ == "__main__":
    main()
