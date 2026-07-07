"""
graph/state.py

The single state object that flows through the whole graph. Fields that
multiple parallel branches write into need a reducer (via Annotated) so
LangGraph knows how to merge concurrent updates instead of overwriting.
"""

import operator
from typing import Annotated, Optional, TypedDict


def merge_dicts(a: dict, b: dict) -> dict:
    """Reducer for version_map: parallel resolve_node branches each add
    one repo's entry; merging is safe since each branch owns a distinct key."""
    return {**a, **b}


class VersionDraft(TypedDict):
    repo: str
    status: str                     # "drafted" | "skipped" | "error"
    commit_hash: Optional[str]
    diff: Optional[str]
    reason: Optional[str]


class PushResult(TypedDict):
    repo: str
    success: bool
    detail: str


class RepoTask(TypedDict):
    """Per-branch input when fanning out with Send -- NOT the full graph state,
    just what one worker needs."""
    repo: str


class VersionBumpTask(TypedDict):
    repo: str
    version_map: dict               # frozen, read-only snapshot


class PushTask(TypedDict):
    repo: str


class ReleaseState(TypedDict):
    # Step 1 output
    changed_repos: list[str]

    # Phase 1 output -- merged across parallel branches via merge_dicts
    version_map: Annotated[dict, merge_dicts]

    # Phase 2 output -- merged across parallel branches via list concat
    drafts: Annotated[list[VersionDraft], operator.add]

    # Human gate output
    approved_repos: list[str]

    # Push phase output
    push_results: Annotated[list[PushResult], operator.add]
