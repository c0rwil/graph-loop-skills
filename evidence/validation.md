# Validation results

Executed 2026-11-09 on macOS. Python 3.14.7, Git, Node.js, Codex CLI 0.167.0,
Claude Code 2.1.304, OpenCode 2.2.6, isolated graphifyy 0.9.104.

## Reproducible checks

`GRAPH_LOOP_GRAPHIFY=/isolated/bin/graphify python3 scripts/validate.py` passes
**30 integration tests**, using real Graphify and temporary Git repositories:

- Exactly the seven requested skills and valid resource references.
- All six platform/provider combinations, idempotent reinstall and dry-run without
  filesystem changes; full pinned dependency installation in a fresh isolated home.
- Uninstall/provider restoration, existing settings and later edits preserved,
  explicit conflict backup/restore, accumulated platform ownership, changing
  central roots, custom config-home paths with spaces and JSONC.
- Isolated-home symlink escapes rejected; CLI/MCP input/schema/path bounds.
- Exact linked-worktree identities, namespaced workspace merge, input provenance,
  failure preservation, code shrink guards, original Git-hook execution/restoration.
- Current source/check receipts, executable-mode freshness, failed native reads,
  source-mutating checks and pipeline exits rejected as verified success.
- Equivalent finding/evidence deduplication and deterministic Graphify reflection,
  shared per-repository/per-criterion contract checks.
- Complete document inputs, exact coverage/hash validation, reuse, pending failures,
  batch-local shrink accounting and no stale cross-document endpoint rebinding.
- Worker timeout/truncation/tool-action contracts, exact reference requirements,
  atomic new-file publication and output-directory replacement attacks.
- Spotify's 34 upstream read/bash routing cases, with the documented targeted
  head/tail exception. Instruction/attachment exemptions are implemented separately.
- Shared MCP initialization, tool schemas and explicit error contracts.

The skill-creator validator also checks all seven frontmatter schemas independently.
Python/JS syntax and source checks prohibit hardcoded personal home paths. Native
CLI config/MCP stores were tested in isolated homes, including custom Codex and
Claude config directories containing spaces. Codex found the registered MCP
server; Claude reported it connected. No auth was copied between harnesses.

## Actual native checks

Authenticated native workers succeeded for **Codex, Claude and OpenCode**:
analysis returned the observed integer seven; reference-matched generation wrote
complete new files, and parent checks imported the generated functions and
explicitly verified return value seven. Claude and OpenCode analysis reports also
cited the actual reference source. Native workers used completion envelopes;
Claude disabled tools/hooks/MCP, Codex used ephemeral/read-only and result-action
rejection, and OpenCode used its authenticated tool-free running-server API.

A real OpenCode 2.2.6 session loaded the plugin and registered all **12** shared
native tools. Loading is lazy; listing before the first session initially showed
no runtime registrations. The final discovery record came from ctx.tool.list in
the running native plugin, rather than a mock.

Live complete-document extraction passed with zero pending inputs on the tiny
fixture. Automatic evidence curation produced three agent-authored findings from
actual current source/check receipts and ran Graphify reflection. These fixture
results validate mechanics, not arbitrary application acceptance or token savings.

A full default installer invocation in a fresh isolated home installed all three
integrations and graphifyy==0.9.104; the symlinked CLI passed doctor. Native and
LiteLLM state/config installation variants are covered by isolated integration tests.

## Contract tests versus live gateway proof

LiteLLM HTTP protocol fixtures exercised Chat Completions, Responses and Messages
with exact aliases and supported effort declarations. Those were local protocol
fixtures, **not a live LiteLLM deployment**. No user gateway URL, aliases or credential
was supplied. Real gateway authentication/model availability/effort support remain
operator validation steps; no invented gateway aliases or credential files exist.

The suite records explicit failures/timeouts. Initial fixture-only issues (temporary
path quoting and concurrent initialization of one smoke fixture) were corrected;
the final generation and parent checks passed. Independent review found installer,
receipt and semantic-cache defects; regression tests cover their fixes.

## Remaining limits and real-home status

Linux/WSL execution is supported by the POSIX implementation but was not run on
those operating systems. Windows outside WSL and OpenCode V1 are not claimed.
Codex's installed native CLI retains read tools in its read-only sandbox; results
containing tool actions are rejected afterward. A completion marker detects common
truncation but cannot prove semantic completeness of generated code. Receipt
provenance alone never proves every acceptance criterion or deployed compatibility.

The real-home plan was dry-run only. Four existing Ponytail/Ponytail Review links
in Claude/OpenCode were reported as conflicts and preserved. Applying replacement
requires an explicit --replace installation, which retains backups. All six
installation variants and full dependency setup completed in isolated homes.
No commit, push or remote was created. Runtime logs, credentials, graphs, semantic
stamps and generated fixture files remain outside the canonical repository.
Restart harnesses after applying installation; review Codex hooks normally in
/hooks and follow native MCP/project trust. No trust bypass was persisted.
