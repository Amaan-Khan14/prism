---
name: review-pipeline-build
description: >
  Working rules for Bob sessions contributing to PRism — an evidence-backed
  code-review pipeline for large or AI-generated pull requests. Use this skill
  whenever implementing or extending any PRism component.
stack: FastAPI + PostgreSQL (SQLAlchemy/Alembic) + Next.js 14 + Tailwind CSS
llm: ZAI/GLM primary, Gemini fallback
---

## What PRism is (one paragraph)

PRism receives a pull request, a diff, and an optional spec. A deterministic
facts engine computes changed lines, real test-coverage data, and
dependency edges. A provider-swappable LLM agent then reasons over those
facts across four parallel facets (intent vs spec, cross-file impact,
test-coverage gaps, risk hazards). A deterministic evidence gate checks every
finding against the computed facts before it reaches the reviewer brief.
Unverified findings go to an appendix, never the main report.

---

## Hard architectural constraints

1. **Facts engine is deterministic.** Changed lines, coverage numbers, and
   dependency edges must come from executable code (git diff, coverage tooling,
   static analysis). Never ask the LLM to guess or infer these values.

2. **LLM is reasoning-only.** The LLM receives facts as structured input and
   produces findings with citations. It never computes facts itself.

3. **Evidence gate is deterministic.** Each finding must cite a specific
   line/file from the computed facts. Findings that fail citation verification
   are moved to an appendix automatically — they are never silently dropped or
   promoted.

4. **Bob is dev-time only.** IBM Bob IDE is a build tool. It must not appear as
   a runtime import, a runtime dependency, or a human-in-the-loop queue step in
   the shipped product.

5. **Bob session screenshots are a required deliverable.** After completing each
   Bob task, screenshot the session consumption summary (Tasks → task header)
   and save it as PNG in `bob_sessions/` following the naming convention in
   `bob_sessions/README.md`. Do not close a task before capturing this.

6. **Data provenance.** All sample repos, specs, and seeded PRs must be
   authored for this project. No client data, no confidential information, no
   scraped social-media content.

---

## Build order (do not skip ahead)

| Step | What gets built |
|------|----------------|
| 1 | DB/API skeleton + facts engine |
| 2 | Evidence gate |
| 3 | Runtime agent + fixture PRs |
| 4 | Frontend with streamed analysis progress |
| 5 | Authored sample repo + seeded PRs |
| 6 | Benchmark scorer |
| 7 | Product polish |
| 8 | README/demo support; capture genuine Bob session evidence |

Before starting any step, confirm the previous step's deliverable is merged.
Stack is confirmed (`stack.confirmed` in codedocket) — do not re-raise `stack.pending`.

---

## Coordination rules

- **Read `.codedocket/knowledge.json` before touching an unfamiliar area.**
  Use `codedocket explore --query <topic>` or read the file directly.
- **Own your files explicitly.** Before editing a file, check git status and
  codedocket notes for concurrent ownership. If Codex or another task owns a
  file, coordinate rather than overlap.
- **Record discoveries.** Non-obvious decisions, constraints, or bug root causes
  go in codedocket via `codedocket record`. Mid-task notes use `codedocket note`.
  Run `codedocket finalize` at session end.
- **Minimal diffs.** Only change what the current task requires. Do not
  refactor adjacent code, add unrequested features, or clean up unrelated areas.

---

## Pipeline shape (quick reference)

```
GitHub PR  ──►  Facts Engine  ──►  [facts: diff lines, coverage, deps]
                                         │
                                    LLM Agent (4 parallel facets)
                                    ├── intent vs spec
                                    ├── cross-file impact
                                    ├── test-coverage gaps
                                    └── risk hazards
                                         │
                                   Evidence Gate (deterministic)
                                    ├── verified  ──►  Risk-ranked brief
                                    └── unverified ──► Appendix
```

The frontend streams live progress as facets complete.

---

## Confirmed stack (reference)

| Layer | Choice |
|---|---|
| Backend API + streaming | FastAPI (Python), SSE via `StreamingResponse` |
| Database | PostgreSQL (local) — SQLAlchemy async + Alembic migrations |
| Frontend | Next.js 14 App Router + Tailwind CSS |
| LLM provider | ZAI/GLM primary; Gemini fallback if ZAI lacks streaming/tool-calls |
| LLM adapter pattern | `BaseProvider` protocol — swap provider by changing one class |

## What this skill does NOT cover

- Stack selection — stack is confirmed; do not re-propose alternatives.
- Benchmark scoring logic (Step 6 — do not implement before Steps 1-5 are done).
- LLM provider internals beyond the thin `BaseProvider` adapter pattern.
