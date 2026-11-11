# Operations and artifacts

`graph-loop` is a symlink to this repository's executable `gl.py`; skills link
through the configurable central folder to the seven canonical source folders.
Use `--state-dir PATH` before subcommands or `GRAPH_LOOP_STATE_DIR` for custom
state. Global flags precede the subcommand. `--home PATH` isolates installation;
no written path may escape it through a custom home setting or symlink.

The installer merges only owned MCP entries, hook groups, command files and marked
instruction blocks. JSONC values are retained when converted to valid JSON for
an owned edit. Reinstall is idempotent; adding a platform retains prior ownership.
Dry-run computes its plan without creating directories, locks or dependency files.
Explicit `--replace` records backups. Uninstall restores unchanged owned values
and replacement backups while preserving subsequent user edits/additions.

External state contains:

- `checkouts/ID/graph.json`: one canonical exact-checkout graph; IDs hash canonical
  Git toplevel paths, not remote URLs or the Git common directory.
- `checkouts/ID/meta.json`: branch, HEAD, dirty/source state and graph hashes.
- `checkouts/ID/documents.json`: validated complete semantic extraction stamps.
- `checkouts/ID/pending/`: oversized/media/deferred/failed work and errors.
- `checkouts/ID/receipts/`: verified or explicitly unverified observations.
- `checkouts/ID/findings/`, `memory/`, `LESSONS.md`: agent conclusions, deduplicated
  Graphify memory exports and deterministic reflection.
- `workspaces/NAME/`: explicit aliased members, merged graph/status, shared-contract
  verification evidence with stable criterion IDs.
- `workers/`: complete isolated input, actual transport output and success/failure
  records, effective model settings and hashes. Treat these as private local data.
- `backups/`, `venv/`, owned OpenCode dependency/plugin and launch directories.

`graph-loop tools` lists shared schemas. `invoke NAME --input JSON` is the generic
CLI equivalent of each MCP/native operation. `mcp` is stdio JSON-RPC, uses bounded
requests, supports initialization/tools/list/tools/call, and returns explicit
`isError` tool errors. No separate server process runs persistently.

Use `workspace register NAME alias=path... --spec alias:path` for registration,
`refresh` per member, `workspace merge NAME`, and `workspace align NAME --run`.
The shared contract template names producers/consumers, API/event/schema/client/
configuration/dependency changes, compatibility and rollout constraints. Successful
local checks do not establish deployed compatibility.

`read FILE --start N --end N` produces source/hash/range receipts. `check --criterion
ID -- PROGRAM ARG...` captures explicit exit status, output hash, bounded excerpt,
working-tree provenance and full local logs. Mutating checks invalidate their
own freshness. Shell pipelines remain unverified even when the outer exit is zero.
Unknown/failed native result formats never become successful verified reads.

`finding --text TEXT --receipts ID... --outcome useful|dead_end|corrected` requires
current verified receipts. Corrections need both `--corrects FINDING_ID` and
`--correction TEXT`. Equivalent evidence/outcomes deduplicate regardless of wording.
Source rereads cannot manufacture corroboration. Graph links refer to actual
relevant node IDs. Reflection is deterministic; findings remain agent-authored.

Primary lifecycle refreshes run at supported new-turn hooks. Claude/Codex Stop and
OpenCode's native idle event refresh and curate from actual receipts/conclusion.
The V2 adapter ignores child sessions. Worker environment/flags prevent recursion.
A failed automatic task is recorded pending, never hidden as completed work.
Git refresh hooks are installed only for explicitly chosen repositories; originals
are backed up and invoked with original arguments/stdin/exit behavior. Shared Git
hook dispatch refreshes only the registered exact checkout, never sibling worktrees
by inference.

Code node shrink beyond 50% requires `refresh --allow-shrink` after source review;
semantic shrink/failure retains prior usable graph and pending status. Graph locks
and atomic JSON publication protect readers. No inferred relationship is a source
receipt, and a missing relationship is not evidence of independence.
