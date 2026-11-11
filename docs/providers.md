# Provider configuration and capabilities

Native and LiteLLM are explicit install choices. Native uses the existing CLI's
own login; nothing copies authentication between providers or harnesses. Gateway
credentials are read only from the named environment variable (default
`LITELLM_API_KEY`). Configuration files may contain its **name**, never its value.
URLs cannot contain userinfo, query parameters or fragments. Secret-valued fields
are rejected at install/CLI/MCP boundaries.

For main sessions use `graph-loop launch PLATFORM`. It supplies an owned launch
overlay/arguments without replacing plain harness provider defaults:

| Harness | LiteLLM main/worker protocol | Native isolated worker |
| --- | --- | --- |
| OpenCode V2 | OpenAI-compatible Chat Completions | Tool-free transient generation on the running authenticated server |
| Codex CLI | Responses API, `wire_api=responses`, named env credential | Ephemeral/read-only, hooks/MCP disabled; tool-action or edit results rejected |
| Claude Code | Anthropic Messages API | Print mode, no tools, strict empty MCP, hooks disabled |

OpenCode's native API returns only text, without full finish metadata. Native
workers therefore require a final completion envelope and reject missing closing
markers, empty/oversized output, errors and timeouts. LiteLLM additionally checks
explicit finish/status fields and rejects tool calls/truncation. Native Codex
cannot disable every built-in tool in the installed CLI; its read-only policy and
result rejection are stated limits, not an OS security guarantee.

Example **non-secret** local configuration (`--config PATH`):

```json
{
  "provider": "litellm",
  "gateway": "https://gateway.example.invalid/v1",
  "credential_env": "LITELLM_API_KEY",
  "main_model": "EXACT_MAIN_ALIAS",
  "workers": {
    "bulk-reader": {"model": "EXACT_READER_ALIAS", "effort": "low"},
    "code-writer": {"model": "EXACT_WRITER_ALIAS", "effort": "medium"}
  },
  "platforms": {
    "codex": {"main_model": "EXACT_RESPONSES_ALIAS"},
    "claude": {"main_model": "EXACT_MESSAGES_ALIAS"}
  },
  "model_capabilities": {
    "EXACT_READER_ALIAS": {"efforts": ["low", "medium"]}
  }
}
```

Use your actual aliases, not these labels. Unspecified LiteLLM workers inherit the
selected per-harness main model. Worker task effort defaults: reader low, writer
medium, document extractor medium, evidence curator low. Effort/variant settings
are sent **only** when `model_capabilities` explicitly declares the selected value
for that exact alias; model/provider support must be verified by the operator.
Native OpenCode uses declared model variants; its transient API does not accept an
arbitrary effort override. Other transports use supported effort settings and
reject a requested effective variant rather than silently ignoring it.
Unrecognized capability is omitted and requested/effective effort remains in the
worker result. Native Claude uses documented Haiku/Sonnet aliases for reader/writer;
other tasks/harnesses inherit the configured primary model absent an override.

`SHUNT_HARNESS` chooses the named script's native adapter (default Codex);
`SHUNT_MIN_LINES` defaults to 350; `SHUNT_TIMEOUT_SECONDS` defaults to 180 and is
bounded at 600. Bulk inputs are capped at 20 files, 60 KB/4000 lines; accepted
answers at 64 KB. Document batches default to 3 files, 60 KB/2000 lines, 2 batches
per refresh, 45 seconds per extraction. All source text is complete, never silently
truncated to fit. No daemon, external model proxy, Portal, AiKA or database ships.

Switching to `--provider native` removes this installation's selection from future
launches/workers. Existing plain-harness settings and authentication were never
rewritten and remain unchanged. An owned OpenCode launch overlay is replaced on
its next gateway launch; it is not a source of persistent native-provider overrides.
