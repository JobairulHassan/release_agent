"""
tools/registry.py

Single place that turns the plain functions in git_tools.py / fs_tools.py
into LangChain @tool objects. The version-bump agent gets BUMP_TOOLS only --
push is intentionally excluded and called directly by push_node instead.
"""

from langchain_core.tools import tool

from tools import git_tools, fs_tools


@tool
def git_log(repo_path: str, branch: str, n: int = 20) -> dict:
    """Get recent commit history for a branch in a repo."""
    return git_tools.git_log(repo_path, branch, n)


@tool
def find_previous_version_cl(repo_path: str, branch: str = "devel", pattern: str = "Bump version") -> dict:
    """Find the most recent version-bump commit on a branch by grepping commit subjects."""
    return git_tools.find_previous_version_cl(repo_path, branch, pattern)


@tool
def git_diff(repo_path: str, ref1: str, ref2: str) -> dict:
    """Diff between two refs (commits/branches) in a repo."""
    return git_tools.git_diff(repo_path, ref1, ref2)


@tool
def git_diff_working_tree(repo_path: str) -> dict:
    """Show uncommitted local changes in a repo."""
    return git_tools.git_diff_working_tree(repo_path)


@tool
def read_file(repo_path: str, file_path: str, ref: str = None) -> dict:
    """Read a file's contents, optionally at a specific git ref."""
    return fs_tools.read_file(repo_path, file_path, ref)


@tool
def write_file(repo_path: str, file_path: str, content: str) -> dict:
    """Write content to a file in the working tree."""
    return fs_tools.write_file(repo_path, file_path, content)


@tool
def git_commit(repo_path: str, message: str) -> dict:
    """Stage and commit local changes on the current branch. Does NOT push."""
    return git_tools.git_commit(repo_path, message)


# Given to the version-bump react agent. Note: no push tool here.
BUMP_TOOLS = [
    git_log,
    find_previous_version_cl,
    git_diff,
    git_diff_working_tree,
    read_file,
    write_file,
    git_commit,
]
