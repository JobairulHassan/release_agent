"""
run.py

Usage:
    python run.py

Runs the graph up to the human_gate interrupt, prints the drafted diffs,
collects your approval, and resumes the graph to push only what you
approved. Safe to re-run: if the process crashes mid-way, the sqlite
checkpointer lets you resume the same thread_id instead of starting over.
"""

import uuid

from langgraph.types import Command

from graph.build_graph import build_graph
from llm.ollama_client import load_settings, get_llm


def print_drafts(drafts):
    print("\n=== Drafted version-bump commits ===\n")
    for d in drafts:
        print(f"[{d['status']}] {d['repo']}")
        if d["status"] == "drafted":
            print(f"  commit: {d['commit_hash']}")
        else:
            print(f"  reason: {d['reason']}")
    print("\n=====================================\n")


def main():
    settings = load_settings()
    llm = get_llm(settings)

    graph = build_graph(settings["checkpoint_db_path"])

    thread_id = str(uuid.uuid4())
    config = {
        "configurable": {
            "thread_id": thread_id,
            "settings": settings,
            "llm": llm,
        }
    }

    print(f"Starting run (thread_id={thread_id})...")
    result = graph.invoke({}, config=config)

    # If human_gate_node fired interrupt(), execution pauses here and
    # `result` contains the interrupt payload rather than a final state.
    if "__interrupt__" in result:
        payload = result["__interrupt__"][0].value
        print_drafts(payload["drafts"])

        raw = input(
            "Enter comma-separated repo names to APPROVE for push (or 'none'): "
        ).strip()
        approved = [] if raw.lower() == "none" else [r.strip() for r in raw.split(",")]

        result = graph.invoke(Command(resume=approved), config=config)

    print("\n=== Push results ===\n")
    for r in result.get("push_results", []):
        status = "OK" if r["success"] else "FAILED"
        print(f"[{status}] {r['repo']}: {r['detail']}")


if __name__ == "__main__":
    main()
