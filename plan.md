# PRism Product Roadmap

## Current snapshot

PRism already has a working application foundation and a substantial review pipeline. This roadmap distinguishes shipped implementation from work still needed for a reproducible demo and hosted release. Update the status column when work is verified.

| Area | Current state |
|---|---|
| Backend and database | FastAPI, PostgreSQL, SQLAlchemy, and Alembic are in use. The local database is at migration `0007` (the current Alembic head). |
| Review pipeline | GitHub PR or raw-diff ingestion, deterministic facts, four review facets, evidence verification, persisted results, and streamed progress are implemented. |
| GitHub | GitHub App sign-in and installation-scoped repository/PR access are implemented. Local sign-in still needs valid OAuth and session/token-encryption configuration. |
| Frontend | Dashboard, Reviews, Repositories, Benchmarks, Method, and per-analysis report routes are implemented. The report uses in-place Findings, Evidence, Coverage, and Diff tabs. |
| Coverage | LCOV/Cobertura parsing, head-SHA validation, provenance, and coverage artifact intake are implemented. Missing, invalid, or mismatched artifacts produce unknown coverage. |
| Storage | Local and private S3 artifact stores are implemented. The private S3 bucket and bucket-scoped EC2 runtime role are deployed; the hosted API passed an S3 write/read/delete check. |
| Benchmarks and demo corpus | The authored shop repository and six seeded PRs are public, with reproducible branches/patches, exact commit SHAs, ground truth, and measured local coverage in `sample_repo/`. The separate two-case benchmark pilot is published; broader measured runs and human timing remain. |
| Deployment | The target is Vercel for the frontend and AWS for the API, database, and private artifact storage. Hosted application infrastructure is not complete. |

The current working tree contains uncommitted application changes. Review and preserve those changes before doing broad cleanup, rebasing, or replacing files.

## Fixed decisions and constraints

| Area | Decision |
|---|---|
| Stack | FastAPI, SQLAlchemy/Alembic, PostgreSQL, Next.js 14 App Router, TypeScript, and Tailwind. |
| Review architecture | Compute deterministic facts first, run four typed review facets concurrently, verify citations against facts, then present a risk-ordered brief. Models must not invent diff lines, dependency edges, or coverage evidence. |
| Model provider | Gemini is the configured default behind the provider adapter. OpenAI is an optional provider selected through `REVIEW_PROVIDER=openai`. Keep secrets server-side. |
| GitHub permissions | Use repository-scoped installation tokens with read-only Metadata, Contents, and Pull Requests access. Do not add `actions:read` without explicit authorization. CI coverage is supplied through the verified PRism artifact-upload API. |
| Coverage | Accept supported coverage artifacts only when their provenance matches the analyzed PR head SHA. Otherwise report coverage as unknown and do not make a coverage-gap claim. |
| Artifact storage | Keep diffs and large artifacts in local storage for development or private S3 in hosted environments. PostgreSQL stores metadata and references; never expose public S3 URLs. |
| Cloud | Target Vercel for Next.js and AWS `ap-south-1` for the backend, private PostgreSQL, and existing private S3 bucket. Use project-scoped infrastructure as code and a least-privilege runtime role. |
| Product scope | Individual GitHub users and user-owned analyses. Keep raw-diff upload available. No team collaboration, billing, or PR write/comment access in v1. |
| Demo data | All sample repositories, specs, and PR fixtures must be authored for PRism and clearly identified as synthetic. Never run arbitrary submitted PR code in the backend. |
| Frontend development | Only one Next.js process should use `frontend/.next` at a time. Coordinate dev/build/start processes to avoid corrupting shared build output. |

## Milestones

| # | Milestone | Status | Remaining work and completion criteria |
|---|---|---|---|
| 0 | Foundation and current changes | **Verified locally (2026-09-27)** | Alembic is at `0007` (head). Backend suite, frontend suite, TypeScript check, and an authenticated local raw-diff review smoke run pass. Application tables were cleared afterward; migration history remains intact. Re-run the end-to-end checks before release. |
| 1 | GitHub connection and PR ingestion | **Implemented; configuration-dependent** | Configure the GitHub App OAuth callback, OAuth client values, cookie/session settings, and token-encryption secret for the target environment. Confirm sign-in, repository selection, PR selection, and exact head/base SHA ingestion with a configured account. |
| 2 | Deterministic facts and evidence gate | **Implemented** | Keep regression coverage for diff line mapping, Python dependency extraction, coverage parsing/provenance, and citation verification. A finding is verified only when all citations satisfy its claim contract; unsupported claims remain unverified. |
| 3 | Runtime review agent and orchestration | **Implemented; provider configuration-dependent** | Configure the chosen provider/model and API key in each environment. Confirm provider errors become visible failed analyses and never fabricated findings. Preserve provider-specific schema handling and bounded context. |
| 4 | Frontend analysis workflow | **Implemented; locally verified** | Keep the purpose-specific sidebar routes and repository-filtered Reviews page. On the per-analysis page, keep Findings/Evidence/Coverage/Diff in the report panel; citation actions should switch tabs and focus the cited diff location. Keep the description collapsed by default. Frontend tests and TypeScript pass; finish responsive and signed-in browser QA before release. |
| 5 | Authored sample repository and seeded PR corpus | **Complete (2026-09-27)** | `sample_repo/` rebuilds a payments/orders/notifications Git repository with six public PRs, patches/bodies, authored specs, issue IDs, exact citation lines, base/head SHAs, and locally measured LCOV artifacts tied to each head. Remote PR SHAs match the manifest. An in-app verified coverage demo still requires a trusted GitHub Actions OIDC upload for the same head SHA. |
| 6 | Benchmark scorer and results | **Two-case pilot published; full benchmark pending** | `backend/benchmarks/score.py` scores exact adjudicated issue IDs, evidence verification, citation accuracy, and measured elapsed time. The pilot has two authored cases. Expand measured runs to the shop corpus, capture timed human reviews, and compare across cases before making product-wide claims. |
| 7 | Hosted deployment | **Backend live; frontend pending** | The backend is live at `https://api.amaankhan.in` on EC2 with HTTPS, private single-AZ RDS PostgreSQL, private S3, project-scoped CloudFormation, and a scoped non-root deployer. Health, browser CORS, database migration, and S3 access are verified. Deploy the frontend to Vercel at `https://prism.amaankhan.in`, set `NEXT_PUBLIC_API_URL=https://api.amaankhan.in`, update the GitHub App OAuth callback/setup URL, then complete AWS OIDC deployment and the hosted smoke checklist. The account currently permits one day of RDS automated backup retention. |
| 8 | Product finish and handoff | **Pending** | Complete setup and architecture documentation, demo seed/reset support, demo script, deployment URLs, benchmark explanation, and release checklist. Keep `bob_sessions/README.md` current and save clearly named PNG evidence for each completed Bob IDE task as required by the project. Confirm a fresh setup can follow the documentation and run the end-to-end demo. |

## Interfaces and data rules

- Preserve user ownership checks on every analysis read/delete path. Historical analyses without an owner must not be exposed to signed-in users.
- Keep analysis spec text explicit; use the PR body as the default and allow supplied spec text to supplement or override it.
- Store artifact checksums, sizes, SHAs, and references in PostgreSQL. Serve artifacts through the authenticated backend API.
- Coverage intake must retain source/run provenance and the associated head SHA. A missing artifact, failed parse, or SHA mismatch means unknown coverage.
- Stream real analysis stages through fetch-based SSE and retain polling/history paths as the recovery path when a stream stalls or disconnects.
- S3 calls from async FastAPI handlers must run outside the event loop using the established executor pattern.

## Release validation checklist

- Apply migrations to a clean database and confirm Alembic reports head `0007` or the later approved head.
- Exercise GitHub sign-in, repository listing, PR selection, raw-diff submission, streamed progress, report tabs, evidence-to-diff navigation, and ownership boundaries with configured credentials.
- Check coverage artifact acceptance for a matching SHA and unknown status for missing, malformed, and mismatched artifacts.
- Run the authored fixtures and benchmark scorer; ensure published claims match measured output.
- Confirm the hosted API reaches private RDS and S3 through its scoped role, frontend/API traffic uses HTTPS, and secrets are not shipped to the browser or committed.
- Follow the README from a fresh checkout and capture the required demo and Bob evidence.

## External setup still required

- GitHub App OAuth client configuration, callback URL, and environment-specific credentials/secrets.
- Chosen Gemini or OpenAI provider credentials and model configuration.
- Frontend deployment and production GitHub App callback/setup URL configuration.
- Production frontend/API domains and Vercel/AWS deployment settings.
- Broader benchmark results, trusted CI coverage upload for the sample PR demo, and remaining Bob IDE evidence.
