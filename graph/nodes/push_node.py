"""
graph/nodes/push_node.py

Only touches repos in state["approved_repos"]. Re-creates a worktree at
the already-committed local commit (recovered from state["drafts"]) rather
than trusting a stale in-memory path, since the earlier worktree was
cleaned up in version_bump_node.
"""

from langgraph.types import Send

from tools.vcs_review_tools import git_push_for_review
from tools.worktree_tools import create_worktree, remove_worktree


def route_to_push(state):
    approved = set(state["approved_repos"])
    drafts_by_repo = {d["repo"]: d for d in state["drafts"]}
    tasks = []
    for repo in approved:
        draft = drafts_by_repo.get(repo)
        if draft and draft["status"] == "drafted":
            tasks.append(Send("push_node", {"repo": repo, "commit_hash": draft["commit_hash"]}))
    return tasks


def push_node(task, config):
    settings = config["configurable"]["settings"]
    repo = task["repo"]
    commit_hash = task["commit_hash"]

    canonical_path = f"{settings['canonical_repo_root']}/{repo}"
    worktree_path = create_worktree(canonical_path, commit_hash, settings["repo_root"])

    try:
        result = git_push_for_review(worktree_path, "devel", settings["push_ref_template"])
        return {"push_results": [{"repo": repo, "success": result["success"], "detail": result["detail"]}]}
    finally:
        remove_worktree(canonical_path, worktree_path)
