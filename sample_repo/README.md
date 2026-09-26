# PRism synthetic shop corpus

This is an entirely authored, synthetic payments/orders/notifications repository for
review demos. It contains no customer code or data. `base/` is the correct starting
point. `cases.json` defines six proposed PRs, their specs, exact defect IDs, and
reproduction steps. Each `cases/<id>/` folder contains the changed source for one
branch. The generated `artifacts/manifest.json` records the exact base and head
commit SHA and citation line for every case.

| PR | Review signal | Expected defect |
|---|---|---|
| [#1 Spec mismatch](https://github.com/Amaan-Khan14/prism-synthetic-shop/pull/1) | PR body vs changed validation | Discount above 100% produces a negative order total |
| [#2 Downstream impact](https://github.com/Amaan-Khan14/prism-synthetic-shop/pull/2) | Cross-file order/notification contract | Receipt understates a charge by 100 times |
| [#3 Coverage gap](https://github.com/Amaan-Khan14/prism-synthetic-shop/pull/3) | Changed line with measured zero hits | Untested expedited payout deducts an unauthorized fee |
| [#4 Transaction atomicity](https://github.com/Amaan-Khan14/prism-synthetic-shop/pull/4) | Failure between state and message writes | Order persists after notification publication fails |
| [#5 Tenant authorization](https://github.com/Amaan-Khan14/prism-synthetic-shop/pull/5) | Tenant-scoped access | Another tenant's order can be read by ID |
| [#6 Concurrent capture](https://github.com/Amaan-Khan14/prism-synthetic-shop/pull/6) | Check/write race | Two concurrent callers can create different captures for one key |

## Rebuild

From the PRism repository root, run:

```bash
python3 sample_repo/build_corpus.py
```

Python 3.9+ and Git are the only requirements. This regenerates the disposable
`sample_repo/.work/repo` with `main` and six `case/<id>` branches. It also
regenerates tracked patches, PR bodies, local line-coverage artifacts, provenance
metadata, and `artifacts/manifest.json`. Commits use fixed author metadata and
dates, so their SHA is reproducible from the same source files. The script runs
the authored unittest suite on every head while measuring executed lines with
Python's standard-library tracer. All six heads currently pass the baseline
suite; these are intentionally missed review defects, not required test failures.

The public repository is
[Amaan-Khan14/prism-synthetic-shop](https://github.com/Amaan-Khan14/prism-synthetic-shop).
All six PRs target its `main` commit recorded in the manifest, and their remote
head SHAs were checked against the local manifest on 2026-09-27. Open a PR URL
through PRism's GitHub flow after connecting that repository to the PRism App.
Alternatively, inspect `artifacts/<id>/pr_body.md` and submit
`artifacts/<id>/pr.patch` through PRism's raw-diff flow. The raw-diff flow has no
head SHA, so its coverage status is correctly **unknown**.

To demonstrate coverage provenance in the app, upload coverage through PRism's
trusted GitHub Actions OIDC workflow for the exact `head_sha`. The tracked local
LCOV reports demonstrate real measured gaps and are tied to the published commit
SHAs; their `local_python_trace` metadata is not a trusted CI identity and must
not be presented as a hosted CI upload.

The `coverage-gap` case has zero measured hits on the changed fee line. Its
reproduction is `settle_payout(1000, 600, 1000, expedited=True)`: the branch
returns `375.00` where the spec requires `400.00`.
