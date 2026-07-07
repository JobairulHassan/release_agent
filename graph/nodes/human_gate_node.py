"""
graph/nodes/human_gate_node.py

Pauses the graph once, after ALL drafts are ready, and waits for a human
to supply the approved repo list. run.py resumes execution with
Command(resume=approved_list) after the reviewer decides.
"""

from langgraph.types import interrupt


def human_gate_node(state):
    approved = interrupt({
        "message": "Review the drafted version-bump commits and approve which to push.",
        "drafts": state["drafts"],
    })
    return {"approved_repos": approved}
