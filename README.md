# Release Version-Bump Agent (LangGraph + local Ollama/Gemma)

Automates the version-bump step of a release process across many repos:
resolve new version numbers for all changed repos (parallel), edit each
repo's devel branch accordingly (parallel), pause for a single human
approval, then push only approved repos.

## Setup

1. `pip install -r requirements.txt`
2. Pull/serve your model locally: `ollama pull gemma2:27b && ollama serve`
   - Set `OLLAMA_NUM_PARALLEL` (env var) above its default (often 1) so
     Ollama can actually batch concurrent requests -- otherwise your
     "parallel" graph branches will just queue behind each other.
3. Edit `config/settings.yaml`:
   - `model_tag` to match your exact locally pulled tag
   - `canonical_repo_root` to wherever your 44 repos are already cloned
   - `step1_script_path` to your REAL step-1 script (a placeholder,
     `step1_check.sh`, is included -- replace its contents)
   - `version_bump_commit_grep` / `push_ref_template` to match your team's
     actual commit-message convention and review system (Gerrit/Perforce)
4. Put your real 44-repo list in `config/repos.txt` (kept for reference;
   the graph itself gets its repo list from step1's output, not this file,
   since step1 already tells you which ones changed).

## Before running the full pipeline

Sanity-check tool-calling reliability with your Gemma tag first:

```python
from llm.ollama_client import get_llm, check_tool_calling_support
print(check_tool_calling_support(get_llm()))
```

Open local models are noticeably less consistent at structured tool use
than hosted frontier models. If `tool_calls_detected` is unreliable across
a few tries, you'll want a JSON-parsing fallback instead of relying on
`bind_tools()` / `create_react_agent` directly -- ask if you want that
variant written out.

## Running

```bash
python run.py
```

This runs step1 → parallel version resolution → parallel version bumping →
pauses and prints all drafted commits → prompts you for approved repo
names → pushes only those.

Safe to re-run: progress is checkpointed to
`state_store/checkpoint_db_path` (sqlite), so a crash mid-run can resume
the same `thread_id` instead of starting over from repo #1.

## Tuning concurrency

`max_concurrency_resolve` / `max_concurrency_bump` in `settings.yaml` cap
how many repos are processed at once. With a single local GPU, more
workers than your GPU can batch just adds queuing delay disguised as
parallelism -- test with 2/4/8 and watch per-request latency, don't just
max it out.

## What's intentionally NOT automated

- `git_push_for_review` is only reachable from `push_node`, after human
  approval -- it is never given to the version-bump agent as a tool.
- The agent is told to skip (not guess) when it can't confidently
  determine a version number or diff pattern -- those show up as
  `status: skipped` in the drafts and need manual handling.

## File map

```
config/          settings + repo list + your real step1 script
graph/           state schema, nodes (step1, resolve, bump, human gate, push), graph wiring
llm/             local Ollama client -- the only file to touch if you swap models/providers
tools/           git/filesystem/worktree/push functions, wrapped as LangChain tools
prompts/         system prompts for the resolve and bump agents
state_store/     sqlite checkpoints + per-run transcripts
workspaces/      ephemeral git worktrees (created/destroyed per repo per run)
run.py           entry point
```
