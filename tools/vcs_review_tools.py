"""
tools/vcs_review_tools.py

Deliberately NOT included in the version-bump agent's toolset. Only
graph/nodes/push_node.py calls this, and only for repos in
state["approved_repos"] after the human gate.
"""

import subprocess


def git_push_for_review(repo_path: str, branch: str, push_ref_template: str) -> dict:
    ref = push_ref_template.format(branch=branch)
    result = subprocess.run(
        ["git", "push", "origin", f"HEAD:{ref}"],
        cwd=repo_path, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return {"success": False, "detail": result.stderr.strip()}
    return {"success": True, "detail": result.stdout.strip()}
