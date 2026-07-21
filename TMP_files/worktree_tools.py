"""
tools/worktree_tools.py

Every repo-edit branch operates in its own `git worktree`, not the
canonical clone. This is what makes parallel edits safe: no shared
working-tree state, easy cleanup on failure, and the human review copy
is isolated from any still-running retry.
"""

import subprocess
import uuid


def create_worktree(canonical_repo_path: str, branch: str, workspace_root: str) -> str:
    from tools.debug_utils import dprint

    run_id = uuid.uuid4().hex[:8]
    repo_name = canonical_repo_path.rstrip("/").split("/")[-1]
    worktree_path = f"{workspace_root}/{repo_name}_{run_id}"

    dprint("WORKTREE CREATE", f"canonical={canonical_repo_path}",
           f"branch={branch}", f"worktree_path={worktree_path}")

    result = subprocess.run(
        ["git", "worktree", "add", worktree_path, branch],
        cwd=canonical_repo_path,
        capture_output=True,
        text=True,
    )
    dprint("WORKTREE CREATE RESULT", f"returncode={result.returncode}",
           result.stdout.strip(), result.stderr.strip())

    if result.returncode != 0:
        raise RuntimeError(f"git worktree add failed: {result.stderr.strip()}")

    return worktree_path


def remove_worktree(canonical_repo_path: str, worktree_path: str, force: bool = True) -> None:
    cmd = ["git", "worktree", "remove", worktree_path]
    if force:
        cmd.append("--force")
    subprocess.run(cmd, cwd=canonical_repo_path, capture_output=True, text=True)
