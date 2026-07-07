"""
graph/nodes/version_resolve_node.py

Phase 1. Runs once per changed repo, in parallel (fanned out via Send in
build_graph.py). Only determines the new version number -- does not touch
files. Result is merged into state["version_map"] via the merge_dicts
reducer, so concurrent branches never collide.
"""

import re

from langgraph.prebuilt import create_react_agent
from langgraph.types import Send

from tools import git_tools
from tools.worktree_tools import create_worktree, remove_worktree
from tools.registry import (
    git_log, find_previous_version_cl, git_diff, git_diff_working_tree,
)

RESOLVE_TOOLS = [git_log, find_previous_version_cl, git_diff, git_diff_working_tree]

with open("./prompts/version_resolver_prompt.txt") as f:
    RESOLVE_SYSTEM_PROMPT = f.read()


def route_to_version_resolve(state):
    """Dispatcher: fan out one Send per changed repo to version_resolve_node."""
    return [Send("version_resolve_node", {"repo": r}) for r in state["changed_repos"]]


def version_resolve_node(task, config):
    settings = config["configurable"]["settings"]
    llm = config["configurable"]["llm"]
    repo = task["repo"]

    repo_name = repo.split("@")[0]
    canonical_path = f"{settings['canonical_repo_root']}/{repo_name}"
    worktree_path = create_worktree(canonical_path, "devel", settings["repo_root"])

    try:
        agent = create_react_agent(llm, tools=RESOLVE_TOOLS)
        result = agent.invoke({
            "messages": [
                ("system", RESOLVE_SYSTEM_PROMPT),
                ("user", f"repo_path={worktree_path}\nDetermine the new version number."),
            ]
        })
        final_text = result["messages"][-1].content

        match = re.search(r"VERSION=(\S+)", final_text)
        new_version = match.group(1) if match else "UNRESOLVED"

        return {"version_map": {repo_name: new_version}}
    finally:
        remove_worktree(canonical_path, worktree_path)
