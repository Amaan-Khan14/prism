# Review benchmark

`cases.json` is the benchmark source of truth. Each case has authored patch/spec inputs, stable ground-truth issue IDs, and measured system runs. Predictions are matched by adjudicated issue ID; this avoids pretending prose similarity is an objective defect match.

Regenerate the aggregate artifacts from `backend/`:

```bash
./.venv/bin/python -m benchmarks.score benchmarks/cases.json --markdown benchmarks/RESULTS.md > benchmarks/RESULTS.json
```

Record only measured runs. Include each system's predicted issue IDs, all-finding count, evidence-gate verified count, citation counts, exact citation adjudication, and elapsed wall time when captured. Leave unavailable baselines out rather than assigning estimated values.

The current pilot contains two authored defects: a discount-boundary validation bug and a stale active-timer regression. Both were detected in the recorded PRism runs after the timer prompt was revised. It is a small quality signal, not a representative evaluation. The separate `sample_repo/` corpus supplies six additional authored PRs for later measurement. Capture timed human reviews before comparing review time.
