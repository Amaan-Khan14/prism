# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

FastAPI backend with PostgreSQL, SQLAlchemy, and Alembic; Next.js 14 App Router with TypeScript and Tailwind CSS; cookie-authenticated REST and server-sent progress updates.

## Users

Engineering leads auditing review quality across large or AI-generated pull requests. Individual GitHub users connect repositories and use PRism to inspect analyses and their supporting evidence.

## Product Purpose

PRism helps reduce review time and missed regressions by checking a pull request against its stated intent, cross-file dependencies, and actual test coverage. Success means a reviewer can understand the highest-risk findings and verify the evidence behind each claim.

## Positioning

PRism combines deterministic code facts with model-proposed findings, then verifies citations against changed lines, dependency edges, and coverage evidence before presenting them as verified. This evidence gate is the product's defining mechanism.

## Operating Context

Users connect GitHub, choose a repository and pull request or provide a pull request URL, watch analysis progress, then inspect a risk-ordered report, cited diff lines, verification state, and coverage provenance. They can return to past analyses. The app also explains the review pipeline and its scope.

## Capabilities and Constraints

- Supports GitHub pull requests and raw-diff analysis.
- Streams analysis progress and falls back to polling when streaming is unavailable.
- Separates verified findings from an unverified appendix and links citations to the diff.
- Coverage claims require coverage evidence for the analyzed commit; missing or mismatched coverage remains unknown.
- GitHub access is user-owned and read-only for repository review. PRism does not execute submitted code or post comments to GitHub.
- The product is a multi-page web app, not an AI-only review bot or single-page mockup.
- A measured two-case benchmark pilot is available; it is too small for product-wide performance claims. Team collaboration, billing, and PR write permissions are outside the current individual-user scope.

## Brand Commitments

The product UI should feel like a mature SaaS review tool and should not resemble a generic AI wrapper. Signed-in product navigation belongs in a sidebar; a separate Dashboard navigation item is unnecessary when that sidebar is present.

## Evidence on Hand

The repository contains authored analysis fixtures, including `backend/tests/fixtures/sample_pr.patch`, plus the public six-PR synthetic shop corpus in `sample_repo/` and real UI flows for repository connection, analysis progress, reports, and history. The measured two-case pilot does not support a broad marketing claim, and there are no customer testimonials.

## Product Principles

- Compute deterministic facts before model reasoning.
- Present findings as verified only when their citations pass the evidence gate.
- Show coverage provenance and preserve unknown when valid evidence is missing.
- Make product claims traceable to real capabilities or measured results.
