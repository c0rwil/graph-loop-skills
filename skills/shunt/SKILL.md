---
name: shunt
description: >
  Spotify Shunt adapted without Portal or AiKA. Route whole-file reads over 350 lines
  and independent predictable generation to native or LiteLLM workers.
license: Apache-2.0
---

# Shunt (Spotify-derived)

This is a portable port of [Spotify Shunt 0.2.0](https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt), pinned and attributed in [provenance](../../provenance.json) and [NOTICE](../../NOTICE). Portal CLI, AiKA modes, and their authentication are removed. The original named interfaces and mode instructions are retained over the shared local transport.

Whole-file reads above `SHUNT_MIN_LINES` (default 350) route to bulk-reader. Targeted ranges, instruction files, small files, and appropriate attachments pass. This manages context, not security. Architectural decisions, debugging and difficult exact edits stay in the parent.

Use sibling `bulk-reader` and `code-writer` for named scripts or equivalent CLI/MCP/native tools. Calls are independent and bounded, with complete input text, timeout, output bounds, source hash validation, and explicit failure/truncation handling. Models use native authentication or the chosen LiteLLM environment credential. No authentication is copied between harnesses.

OpenCode uses authenticated tool-free transient generation on the running V2 server; Claude print workers disable tools/hooks/MCP; Codex workers are ephemeral/read-only and reject any tool-action result. Codex rejection is after observation and does not make its read-only sandbox an OS isolation boundary. [Provider differences](../../docs/providers.md).
