# PRism — frontend

Next.js 14 (App Router) + TypeScript + Tailwind CSS. Cookie-authenticated
against the PRism FastAPI backend.

## Quick start

```bash
# 1. Install dependencies
npm install

# 2. Configure the backend URL (defaults to http://localhost:8000)
cp .env.example .env.local

# 3. Start the dev server (expects the backend on :8000)
npm run dev
```

Open http://localhost:3000. The backend's `CORS_ALLOWED_ORIGINS` and
`AUTH_FRONTEND_URL` must include `http://localhost:3000` (they do by default).

## Product flow

1. **Sign in** — the nav's “Sign in with GitHub” starts `GET /auth/github/login`
   (GitHub App OAuth with PKCE). The callback sets the PRism session cookie and
   returns to the frontend.
2. **Connect repositories** — the dashboard's “Connect GitHub App” button opens
   `GET /auth/github/install`; the installation callback links the installation
   to the PRism user and returns with `?github_app=connected`.
3. **Submit a PR** — paste a GitHub PR URL on the dashboard. `POST /analyses`
   schedules the analysis in the backend (facts → four facets → evidence gate).
4. **Watch live progress** — the analysis page streams
   `GET /analyses/{id}/stream` (SSE via fetch), falling back to polling
   `GET /analyses/{id}` if the stream stalls.
5. **Read the report** — verified findings with citations linked into the
   private diff (`GET /analyses/{id}/diff`), an unverified appendix, coverage
   provenance, and verification state.
6. **History** — the dashboard lists prior analyses from `GET /analyses`.

## Scripts

| Command | Purpose |
| --- | --- |
| `npm run dev` | Dev server on :3000 |
| `npm run build` | Production build |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | Vitest + Testing Library suite |

## Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | PRism API base URL |

## Tests

`npm test` covers the API client (error mapping, cookie handling), the SSE
parser and stream lifecycle, the unified-diff parser and citation→diff lookup,
and the main flows: dashboard submission (success, backend error, validation),
live progress → report transition, and the completed report (brief, verified
findings, unverified appendix, coverage provenance, diff linking).
