# Verified source and compatibility references

Checked 2026-11-09 against Codex CLI 0.167.0, Claude Code 2.1.304 and OpenCode 2.2.6.
The local CLI help and installed OpenCode 2.2.6 client/plugin/schema types were
inspected alongside official documentation. Graphify 0.9.104 was installed into
an isolated environment and exercised against actual Git repositories/worktrees.

- [Graphify quickstart](https://docs.graphify.com/open-source/quickstart),
  [source](https://github.com/Graphify-Labs/graphify): isolated graphifyy dependency,
  code extraction with GRAPHIFY_OUT, save-result and deterministic reflect.
- [Spotify Shunt source](https://github.com/spotify/portal-ai-plugins/tree/main/plugins/shunt):
  pinned commit and original source hashes are recorded in provenance.json.
  Read routing cases are retained under tests/upstream. Portal/AiKA transport is
  replaced; changed scripts/hooks/skills identify their origin and modifications.
  The intentional routing difference allows explicitly bounded head/tail counts.
- [Ponytail](https://github.com/DietrichGebert/ponytail): exactly two requested
  skills from a pinned source commit; full MIT notice retained.
- [Codex hooks](https://learn.chatgpt.com/docs/hooks),
  [configuration reference](https://learn.chatgpt.com/docs/config-file/config-reference),
  [skills](https://developers.openai.com/codex/skills): user hooks/config,
  Responses-only custom providers, env_key, skill discovery and trust review.
- [Claude headless](https://code.claude.com/docs/en/headless),
  [hooks](https://code.claude.com/docs/en/hooks),
  [gateway documentation](https://code.claude.com/docs/en/llm-gateway): print mode,
  tool/MCP/hook disabling and Messages gateway environment. Worker flags were
  confirmed with the installed CLI and actual authenticated requests.
- [OpenCode providers](https://opencode.ai/docs/providers/),
  [server plugin API](https://opencode.ai/docs/build/plugins/server/),
  [skills](https://opencode.ai/docs/skills/): current V2 providers configuration,
  native JSON-schema tools, prompt/context/tool hooks and session.idle events.
  The installed 2.2.6 client maps tool-free transient generation to
  POST /api/experimental/generate/text. Plugin/schema dependencies were inspected
  in an isolated owned directory. The thin plugin uses the harness's native JSON
  schema interface; no additional schema/SDK dependency is needed at execution time.

No Spotify service endpoints, personal skills, credentials, user-home paths,
Portal CLI, AiKA clients or model-proxy daemon are copied into the repository.
