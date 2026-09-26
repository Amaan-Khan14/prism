# PRism review benchmark · pilot

Pilot corpus: two authored cases. Results are directional and not product-wide performance claims.

| System | Cases | Precision | Recall | F1 | Evidence verified | Citation accuracy | Mean time |
|---|---:|---:|---:|---:|---:|---:|---:|
| PRism (Gemini) | 2 | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 8.08s |
| Unstructured Gemini | 1 | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 1.55s |

## Counts

| System | TP | FP | FN | Timed cases |
|---|---:|---:|---:|---:|
| PRism (Gemini) | 2 | 0 | 0 | 2 |
| Unstructured Gemini | 1 | 0 | 0 | 1 |

Metrics use exact, adjudicated issue IDs per case. Missing systems and timing data are omitted, not imputed.

Both updated PRism runs used the configured gemini-3.8-flash primary with gemini-3.1-flash-lite fallback; latency is one local run and includes model/API response time. The unstructured Gemini baseline is historical.
Human timed review is not measured yet. Defect precision/recall exclude non-defect metadata claims. The updated prompt no longer emits the unsupported coverage-unknown claim present in the earlier PRism run.
Updated PRism correctly cited the discount defect at src/discount.py:4. The unstructured response cited src/discount.py:1, so its defect detection was correct but its citation was not.
Added an authored timer-reconfiguration regression case. The first run missed it; after adding an explicit setting-change/in-flight-work trace and a citation anchor for the changed setting assignment, the reviewer detected it and cited src/mover.js:24 in 9.36 seconds.
The connected human-simulator#2 demo still has no supported defect: its setResumeAfterMs implementation clears and replaces the timer while the mover is running and yielded. Copilot's remaining suggestions are test/documentation advice rather than confirmed runtime bugs.
