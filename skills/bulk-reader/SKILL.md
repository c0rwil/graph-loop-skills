---
name: bulk-reader
description: Spotify Shunt bulk file analysis for files over 350 lines, questions across 3+ files, or large diffs; independent bounded worker context.
license: Apache-2.0
---

# Bulk Reader

Modified Spotify Shunt skill (Apache-2.0; [NOTICE](../../NOTICE)). Use:

```sh
graph-loop bulk-read --question 'Trace validation with file:line citations' --paths src/validate.py tests/test_validate.py --harness codex
```

`claude` and `opencode` use their own authentication. The named `skills/shunt/scripts/bulk-read` entrypoint supports the same `--question` and `--paths` interface. Each call is independent; follow-ups resend the complete declared files to the worker, never through the primary conversation. Keep the parent focused on decisions and exact excerpts.

Input limit: 20 files, 60 KB and 4000 lines; split oversized corpora. Output is an unverified agent observation. Verify exact source and line numbers before edits. Do not substitute a bulk summary for document semantic-extraction input. [Worker instructions](../../workers/bulk-reader.md).
