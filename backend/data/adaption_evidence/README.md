# Adaption evidence bundle

- `brief.txt`: exact plain-English brief used by the MirageNet SDK integration.
- `session_brief.txt`: exact brief for labelled session trajectories used by Phase 2.
- `uploaded_decoy_source.jsonl`: byte-identical copy of the user-supplied JSONL export used to build the reproducible local cache.
- `uploaded_decoy_source.json` and `uploaded_decoy_source.csv`: byte-identical copies of the user's additional exports, retained as supporting evidence.
- `job_manifest.json`: row counts, filtering threshold, score provenance, dataset identifiers, status, and screenshot provenance.
- `adaption_job_screenshot.jpg`: user-provided screenshot of the Adaption dataset list. It shows `decoy_file_artifacts` as **Running**; it does not show a completed quality evaluation.
- `sessions.jsonl`: local labelled session fallback when `ADAPTION_API_KEY` is not configured; when configured, the integration replaces this with the downloaded Adaption session dataset.
- `replay_results.jsonl`: append-only results from black-box session replays.

## Important provenance note

The external dataset ID in the manifest came from the Adaption URL supplied by the user. This app did not launch that external job, and the screenshot shows it still running. No authenticated SDK run was possible in this environment because no `ADAPTION_API_KEY` was supplied. The cached rows are therefore labeled `cache`; per-row `quality_score` values use the transparent `cache_rubric` unless the downloaded row itself contains a numeric score. Adaption's dataset-level evaluation score is stored separately and is never copied onto individual rows.

The application can run the official SDK integration when `ADAPTION_API_KEY` is set. It uses `datasets.invent`, waits for completion, downloads JSONL, and requests `datasets.get_evaluation`; SDK response IDs and quality results are recorded in the manifest. If a screenshot of the completed job is needed, upload a real screenshot from the Adaption UI through Decoy Lab.
