"""
tools/fs_tools.py
"""

import subprocess


def read_file(repo_path: str, file_path: str, ref: str = None) -> dict:
    """Read a file's contents, optionally at a specific git ref (e.g. a past commit)."""
    if ref:
        result = subprocess.run(
            ["git", "show", f"{ref}:{file_path}"],
            cwd=repo_path, capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        return {"content": result.stdout}

    with open(f"{repo_path}/{file_path}") as f:
        return {"content": f.read()}


def write_file(repo_path: str, file_path: str, content: str) -> dict:
    with open(f"{repo_path}/{file_path}", "w") as f:
        f.write(content)
    return {"written": file_path}
