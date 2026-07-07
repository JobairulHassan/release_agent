"""
tools/git_tools.py

Plain functions -- no framework dependency here. tools/registry.py wraps
these with @tool so the react agent can call them. Keeping them plain
also means they're independently unit-testable.
"""

import subprocess


def _run(cmd, cwd=None, timeout=60):
    try:
        result = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as e:
        # System error -- controller/caller should retry, not the model.
        raise TimeoutError(f"Command timed out: {' '.join(cmd)}") from e

    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr.strip()}")
    return result.stdout.strip()


def git_log(repo_path: str, branch: str, n: int = 20) -> dict:
    """Get recent commit history for a branch."""
    out = _run(["git", "log", branch, f"-{n}", "--pretty=%H|%s"], cwd=repo_path)
    commits = []
    for line in out.splitlines():
        h, _, subject = line.partition("|")
        commits.append({"hash": h, "subject": subject})
    return {"commits": commits}


def find_previous_version_cl(repo_path: str, branch: str = "devel", pattern: str = "Bump version") -> dict:
    """Find the most recent version-bump commit on a branch by grepping subjects."""
    out = _run(
        ["git", "log", branch, f"--grep={pattern}", "-1", "--pretty=%H|%s"],
        cwd=repo_path,
    )
    if not out:
        return {"found": False}
    h, _, subject = out.partition("|")
    return {"found": True, "hash": h, "subject": subject}


def git_diff(repo_path: str, ref1: str, ref2: str) -> dict:
    """Diff between two refs/commits."""
    out = _run(["git", "diff", ref1, ref2], cwd=repo_path)
    return {"diff": out}


def git_diff_working_tree(repo_path: str) -> dict:
    """Show uncommitted local changes."""
    out = _run(["git", "diff"], cwd=repo_path)
    return {"diff": out}


def git_commit(repo_path: str, message: str) -> dict:
    """Stage and commit local changes on the current branch (no push)."""
    _run(["git", "add", "-A"], cwd=repo_path)
    _run(["git", "commit", "-m", message], cwd=repo_path)
    commit_hash = _run(["git", "rev-parse", "HEAD"], cwd=repo_path)
    return {"committed": commit_hash}


def get_latest_commit_hash(repo_path: str) -> str:
    """Non-tool helper used by nodes to check whether the agent committed anything."""
    return _run(["git", "rev-parse", "HEAD"], cwd=repo_path)
