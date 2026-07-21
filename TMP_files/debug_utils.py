"""
tools/debug_utils.py

Set RELEASE_AGENT_DEBUG=1 in your shell (or .env) to turn on verbose
tracing across the pipeline. Left in place permanently -- costs nothing
when off, and you'll need it again after any prompt/gateway change.
"""

import os

DEBUG = os.getenv("RELEASE_AGENT_DEBUG") == "1"


def dprint(tag: str, *args):
    if not DEBUG:
        return
    print(f"\n----- [{tag}] -----")
    for a in args:
        print(a)
    print(f"----- end [{tag}] -----\n")
