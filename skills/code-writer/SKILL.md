---
name: code-writer
description: Spotify Shunt reference-matched generation for tests, configs, stubs or adapters where over 80 percent follows existing patterns.
license: Apache-2.0
---

# Code Writer

Modified Spotify Shunt skill (Apache-2.0; [NOTICE](../../NOTICE)). Use:

```sh
graph-loop code-write --spec 'Generate a sibling test covering empty input' --reference tests/test_existing.py --target tests/test_new.py --harness codex
```

A reference is mandatory. Each call is independent. Match exact APIs, names, style and patterns. No new abstractions or invented dependencies. The parent handles the remaining judgment, review, integration and verification. [Worker instructions](../../workers/code-writer.md).

A direct-write target must be NEW and its parent must already exist. Complete output publishes atomically without overwriting files or symlinks. Omit `--target` for code on stdout. The named `skills/shunt/scripts/code-write` entrypoint preserves Spotify's `--spec`, `--reference`, `--target` interface. Follow-ups use the last generated file as a new explicit reference.
