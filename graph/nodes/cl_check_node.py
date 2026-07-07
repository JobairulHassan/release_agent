"""
graph/nodes/cl_check_node.py

Runs your existing, already-automated step-1 script (devel vs master CL
hash comparison across all repos) and feeds its output into the graph
state as changed_repos.
"""

import subprocess


def cl_check_node(state, config):
    settings = config["configurable"]["settings"]
    script_path = settings["step1_script_path"]

    result = subprocess.run(
        [script_path], capture_output=True, text=True, timeout=300
    )
    if result.returncode != 0:
        raise RuntimeError(f"step1 script failed: {result.stderr.strip()}")

    changed_repos = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return {"changed_repos": changed_repos}
