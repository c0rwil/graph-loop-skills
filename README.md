# Graph Loop Skills

A portable spec-driven workflow for OpenCode, Codex CLI and Claude Code CLI:
request → behavior contract → scoped graph context → smallest coherent change →
relevant checks → graph refresh → durable evidence and reflection.

Exactly seven skills ship: **graphify, graph-loop, ponytail, ponytail-review,
shunt, bulk-reader, code-writer**. One standard-library Python runtime serves
CLI, MCP and thin native adapters. Spotify's Shunt is ported without Portal/AiKA.
The upstream licenses, pinned versions, modifications and hashes are in
[NOTICE](NOTICE), [licenses](licenses/) and [provenance.json](provenance.json).

## Install

Requirements: Python 3.11+, Git, macOS/Linux/WSL. OpenCode V2 is the validated
native adapter; installed versions and actual checks are in [validation](evidence/validation.md).
The default source location is `~/PycharmProjects/graph-loop-skills`; cloning
anywhere else works. The repository remains the canonical source.

```sh
cd ~/PycharmProjects/graph-loop-skills
python3 gl.py install --platform all --provider native --dry-run
python3 gl.py install --platform all --provider native
```

Select one or more platforms, e.g. `--platform codex claude`. Dependency setup
pins `graphifyy==0.9.104` in the external owned state environment. It never runs
`graphify install`, installs unrelated skills, or copies authentication.

Defaults:

- Central skill links: `~/.local/share/graph-loop/skills`.
- Runtime, graphs, evidence, backups and dependency environments:
  `~/.local/state/graph-loop`.
- CLI link: `~/.local/bin/graph-loop` (ensure that directory is on PATH).

```sh
python3 gl.py --state-dir '/path with spaces/state' install --platform codex \
  --provider native --skills-dir '/path with spaces/skills' \
  --graphify /existing/isolated/bin/graphify --skip-deps
```

Use `--home /tmp/isolated-home` **before** the subcommand for isolated installation.
Custom config-home environment variables are honored when they stay inside that
home; symlink escapes are rejected. Normal installs honor `CODEX_HOME`,
`CLAUDE_CONFIG_DIR`, `OPENCODE_CONFIG_DIR`, and `XDG_CONFIG_HOME`.
`GRAPH_LOOP_STATE_DIR` is an alternative to passing `--state-dir` on every call.

Conflicts fail before installation changes. Explicit `--replace` preserves
backups and replaces conflicting owned files/skill links. Do not add that flag
unless replacing the reported paths is intended. Existing unrelated settings,
providers, permissions, instructions, hooks and skills remain intact. Later edits
to owned files are retained on uninstall. [Detailed operations](docs/operations.md).

## LiteLLM or native providers

The installation choice controls Graph Loop workers and `graph-loop launch`.
Plain harness commands retain their independent provider defaults. This makes
switching reversible without rewriting users' native settings or authentication.
Use the provider-aware launcher for the chosen main model:

```sh
# Set LITELLM_API_KEY securely in your environment; never in a file here.
python3 gl.py install --platform all --provider litellm \
  --gateway https://gateway.example.invalid/v1 --credential-env LITELLM_API_KEY \
  --main-model EXACT_MAIN_ALIAS \
  --worker-model bulk-reader=EXACT_READER_ALIAS \
  --worker-model code-writer=EXACT_WRITER_ALIAS

graph-loop launch codex
graph-loop launch claude
graph-loop launch opencode
```

Replace the example URL and aliases with your exact gateway configuration.
Credential-bearing URLs and secret-valued configuration fields are rejected.
OpenCode uses Chat Completions, Codex uses Responses, Claude uses Messages.
Unspecified gateway workers inherit the main alias. Per-harness overrides,
effort/variant capability declarations, and environment-only authentication are
covered in [providers](docs/providers.md). Native mode uses each CLI's own login.

```sh
python3 gl.py install --platform all --provider native
```

The native switch changes only owned selection/launch overlays. No authentication
is transferred between harnesses; independent user provider edits remain untouched.

## Shared contracts and repositories

Only explicit exact checkouts/worktrees are registered. No unrelated repositories
are scanned or selected by name.

```sh
graph-loop workspace register product \
  api=/path/to/api-checkout web=/path/to/web-checkout --spec api:specs/behavior.json
graph-loop --repo /path/to/api-checkout refresh
graph-loop --repo /path/to/web-checkout refresh
graph-loop workspace merge product
graph-loop workspace align product --run
```

Use [the shared behavior contract template](specs/behavior-contract.json).
Acceptance IDs remain stable; checks have repository owners. Producer/consumer
ownership, supported change types, compatibility expectations and rollout order
are explicit. Verification produces per-repository/per-criterion receipts.

Each exact checkout owns one canonical graph under external state. Workspace
merges namespace IDs and record aliases, absolute source paths, branch, HEAD,
dirty source state and input graph hashes. Failures preserve the prior published
graph and expose pending status. Checkout alignment does **not** establish deployed
compatibility; inferred links require source confirmation; no graph path does not
prove independence.

```sh
graph-loop --repo /path/to/api-checkout query 'validation callers'
graph-loop --repo /path/to/api-checkout path 'producer' 'consumer'
graph-loop --repo /path/to/api-checkout explain 'validate'
graph-loop --repo /path/to/api-checkout read src/validation.py --start 20 --end 45
graph-loop --repo /path/to/api-checkout check --criterion AC-1 -- python3 -m unittest
```

## Automatic work

Primary-turn hooks refresh code; Stop/idle refreshes after edits. Optional explicit
`graph-loop --repo PATH git-hooks` preserves existing post-commit, post-checkout,
post-merge and post-rewrite hooks and adds code refresh. Workspace inputs remerge
after local refresh. Workers suppress recursive lifecycle hooks.

Changed eligible text is extracted from its **complete input**, in bounded batches.
Unchanged hashes reuse stamps. Media, oversized, failed and incomplete inputs
remain pending. Exact coverage/source hashes and extraction provenance are checked;
shrink guards retain prior graphs. Shunt summaries never replace extraction input.

Exact source reads and checks create receipts with checkout/source/output hashes,
ranges or explicit exits, timestamps and session/tool identity when available.
Native hooks verify only supported result shapes and stable pre/post source states.
Graph queries and worker summaries remain unverified observations. A pipeline's
outer exit or absent exit metadata cannot establish check success.

Completed primary turns curate at most three meaningful, explicitly agent-authored
findings from current verified receipts and the final conclusion. Equivalent
source/check evidence and outcomes deduplicate; corrected findings require actual
corrections. Actual related graph nodes link when available. Saving findings runs
deterministic Graphify reflection. Provenance alone never proves all criteria.

## Shunt

Spotify's named interfaces remain available:

```sh
graph-loop bulk-read --question 'Trace validation and tests' --paths src/validate.py tests/test_validate.py --harness claude
graph-loop code-write --spec 'Generate a sibling test for empty input' \
  --reference tests/test_existing.py --target tests/test_new.py --harness codex
```

Whole-file reads over 350 lines route to a worker. Targeted reads, instruction
files, small files and suitable attachments pass. Context routing is not a security
boundary. Generation needs a reference, and direct-write targets must be **new**
with an existing parent. Publication is atomic and never overwrites files or
symlinks. Calls are independent, bounded and timed out; incomplete results fail.

OpenCode uses the running V2 server's authenticated tool-free transient-generation
API. Claude uses tool-free print workers with hooks/MCP disabled. Codex uses
read-only ephemeral workers and rejects results containing tool actions or edits;
its sandbox still permits reads, so this is not a claim of pre-execution tool
elimination. The parent retains architecture, debugging, hard edits and verification.

## Prompts, tools, updates and removal

Kickoff, align, finish, graphify, workspace, bulk-reader and code-writer templates
ship under `prompts/`. Claude/OpenCode receive native `graph-loop-*` command files.
Codex uses documented `$graph-loop` skill invocation and `graph-loop prompt NAME`;
no unsupported slash commands are invented. The MCP server and OpenCode native
adapter expose the same validated 12 operations as the CLI.

```sh
graph-loop doctor
graph-loop prompt kickoff --request 'Implement the requested behavior'
python3 gl.py install --platform all --provider native --dry-run  # update preview
python3 gl.py install --platform all --provider native            # update links/config
graph-loop uninstall --dry-run
graph-loop uninstall
```

Uninstall restores unchanged owned settings and replaced-file backups, preserving
later edits and unrelated additions. Historical evidence/graphs/dependencies remain
outside the repository. Restart harnesses after installation. Codex requires its
normal project/hook trust review in `/hooks`; the installer never fabricates trust.
MCP activation follows each harness's normal trust flow.

## Validation

```sh
GRAPH_LOOP_GRAPHIFY=/isolated/bin/graphify python3 scripts/validate.py
python3 scripts/package.py
```

The suite uses isolated homes, real Git/Graphify, upstream Spotify routing cases,
local gateway protocol fixtures and worker process contracts. [Actual live checks
and limits](evidence/validation.md) distinguish authenticated model calls from
contract tests. No commit, push or remote creation is performed by setup.
