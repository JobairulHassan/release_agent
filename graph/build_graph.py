"""
graph/build_graph.py

Wires the full pipeline:
  step1 -> (fan out) version_resolve -> (fan out, after ALL resolved) version_bump
        -> human_gate (interrupt) -> (fan out approved) push -> END

LangGraph automatically waits for all Send-spawned branches of a node to
finish before firing the next edge, so version_bump_node only starts once
version_map is fully populated -- no manual barrier/join code needed.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver

from graph.state import ReleaseState
from graph.nodes.cl_check_node import cl_check_node
from graph.nodes.version_resolve_node import version_resolve_node, route_to_version_resolve
from graph.nodes.version_bump_node import version_bump_node, route_to_version_bump
from graph.nodes.human_gate_node import human_gate_node
from graph.nodes.push_node import push_node, route_to_push


def build_graph(checkpoint_db_path: str):
    builder = StateGraph(ReleaseState)

    builder.add_node("step1_node", cl_check_node)
    builder.add_node("version_resolve_node", version_resolve_node)
    builder.add_node("version_bump_node", version_bump_node)
    builder.add_node("human_gate_node", human_gate_node)
    builder.add_node("push_node", push_node)

    builder.add_edge(START, "step1_node")

    # Fan out: one branch per changed repo
    builder.add_conditional_edges("step1_node", route_to_version_resolve, ["version_resolve_node"])

    # Fan out again, only once ALL resolve branches are done (implicit join)
    builder.add_conditional_edges("version_resolve_node", route_to_version_bump, ["version_bump_node"])

    # Fan-in: once all bump branches are done, proceed to the single human gate
    builder.add_edge("version_bump_node", "human_gate_node")

    # After human approval, fan out only to approved repos
    builder.add_conditional_edges("human_gate_node", route_to_push, ["push_node", END])

    builder.add_edge("push_node", END)

    checkpointer = SqliteSaver.from_conn_string(checkpoint_db_path)
    return builder.compile(checkpointer=checkpointer)
