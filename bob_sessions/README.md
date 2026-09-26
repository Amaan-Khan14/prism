# Bob Sessions — Hackathon Evidence

This folder contains **required hackathon deliverables**: session summary
screenshots from IBM Bob IDE proving Bob was used to build PRism.

## How to capture a screenshot

1. In Bob IDE, open the **Tasks** panel (left sidebar or ⌘T).
2. Select a completed task.
3. Click the **task header** to open the session consumption summary.
4. Screenshot the full summary panel.
5. Save as **PNG** in this folder using the naming convention below.

## Naming convention

```
prism_task<NN>_<short_description>_summary.png
```

Examples:
- `prism_task01_db_skeleton_summary.png`
- `prism_task02_facts_engine_summary.png`
- `prism_task03_evidence_gate_summary.png`
- `prism_task04_runtime_agent_summary.png`
- `prism_task05_frontend_streaming_summary.png`
- `prism_task06_benchmark_scorer_summary.png`

## Task index (update as tasks are completed)

| # | Task description | Screenshot file | Status |
|---|---|---|---|
| 01 | DB/API skeleton + storage layer | `prism_task01_db_skeleton_summary.png` | completed |
| 01b | Facts engine (deterministic diff + Python deps + coverage stub) | `prism_task02_facts_engine_summary.png` | completed |
| 02 | Evidence gate | — | completed |
| 03 | CI coverage artifacts + exact-SHA validation (roadmap item 3) | `prism_task03_ci_coverage_sha_validation_summary.png` | completed |
| 03b | Activate and demonstrate CI coverage upload for Codedocket PR #1 | — | blocked: Codedocket checkout/workflow is outside this workspace; upstream workflow change and hosted run required |
| 04 | Runtime agent + fixture PRs | — | pending |
| 05 | Frontend with streamed progress | — | pending |
| 06 | Authored sample repo + seeded PRs | — | implementation published; Bob summary screenshot pending |
| 07 | Benchmark scorer | — | pending |
| 08 | Product polish | — | pending |
| 09 | README/demo support | — | pending |

## Important

- `1st-task.png` is the only PNG currently present. The named screenshots in the
  task index still need to be captured or located before submission.
- One screenshot per **Bob task** (not per conversation turn).
- Capture the summary *before closing the task* — it cannot be recovered after.
- PNG only; no HEIC, JPG, or PDF.
- Do not commit screenshots of anything containing secrets, API keys, or
  personal data.
