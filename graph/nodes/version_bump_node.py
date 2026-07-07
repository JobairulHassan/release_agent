"""
graph/nodes/version_bump_node.py

Phase 2. Runs once per changed repo, in parallel, AFTER version_map is
fully resolved (LangGraph waits for all version_resolve_node branches to
finish before this dispatcher fires, since it depends on state["version_map"]).
Each branch gets the full, frozen version_map read-only -- safe for the
cross-repo "Requires: other_repo >= X" case with no coordination needed.
"""

from langgraph.prebuilt import create_react_agent
from langgraph.types import Send

from tools import git_tools
from tools.worktree_tools import create_worktree, remove_worktree
from tools.registry import BUMP_TOOLS

with open("./prompts/version_bump_prompt.txt") as f:
    BUMP_SYSTEM_PROMPT = f.read()


def route_to_version_bump(state):
    """Dispatcher: fan out one Send per repo, now that version_map is complete."""
    return [
        Send("version_bump_node", {"repo": repo, "version_map": state["version_map"]})
        for repo in state["version_map"]
    ]


def version_bump_node(task, config):
    settings = config["configurable"]["settings"]
    llm = config["configurable"]["llm"]
    repo = task["repo"]
    version_map = task["version_map"]
    new_version = version_map.get(repo)

    if new_version == "UNRESOLVED" or new_version is None:
        return {"drafts": [{
            "repo": repo, "status": "skipped", "commit_hash": None,
            "diff": None, "reason": "version could not be resolved in phase 1",
        }]}

    canonical_path = f"{settings['canonical_repo_root']}/{repo}"
    worktree_path = create_worktree(canonical_path, "devel", settings["repo_root"])

    try:
        agent = create_react_agent(llm, tools=BUMP_TOOLS)
        user_msg = (
            f"repo_path={worktree_path}\n"
            f"new_version={new_version}\n"
            f"version_map={version_map}\n"
            "Apply the version bump."
        )
        result = agent.invoke({
            "messages": [("system", BUMP_SYSTEM_PROMPT), ("user", user_msg)]
        })
        final_text = result["messages"][-1].content

        # Check whether the agent actually committed, rather than trusting its
        # summary text alone -- ground truth is the git log.
        try:
            commit_hash = git_tools.get_latest_commit_hash(worktree_path)
            diff = git_tools.git_diff(worktree_path, f"{commit_hash}~1", commit_hash)["diff"]
            status = "drafted"
        except Exception:
            commit_hash, diff, status = None, None, "skipped"

        return {"drafts": [{
            "repo": repo, "status": status, "commit_hash": commit_hash,
            "diff": diff, "reason": final_text,
        }]}
    finally:
        # NOTE: only remove the worktree after the commit is captured above.
        # If you want the human reviewer to inspect the live worktree instead
        # of just the stored diff text, skip cleanup here and do it in
        # push_node after approval/rejection instead.
        remove_worktree(canonical_path, worktree_path)
