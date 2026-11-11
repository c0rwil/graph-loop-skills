# Graph Loop Skills maintenance

The seven folders under skills/ are the canonical bundled skills. Do not add
unrelated skills or copy user configuration into this repository. Runtime state,
graphs, receipts, authentication, dependencies and generated distributions belong
outside the source tree. Preserve Spotify/Ponytail licenses and pinned provenance.

Use Python 3.11+ standard-library code for the shared runtime and thin native
adapters. Verify harness fields against installed versions and official sources.
Keep native authentication separate per harness; never persist credential values.
Test installers in isolated homes, including ownership restoration and later edits.

Validate with GRAPH_LOOP_GRAPHIFY pointing to an isolated graphifyy==0.9.104
executable: python3 scripts/validate.py. Live smoke is opt-in and uses existing
harness authentication. Distinguish fixtures from actual model/gateway checks.
Do not commit, push or create a remote without an explicit user request.
