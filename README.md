# Finaimatic GTM Framework

Local-first GTM stack. SQLite backend + Next.js frontend for managing and viewing leads. Manage campaigns through instantly.

## Structure

```
framework/
├── gtmbackend/   # Python/FastAPI — SQLite leads database + REST API
└── gtmfrontend/  # Next.js 16 — leads dashboard UI
```

## gtmbackend

FastAPI server backed by SQLite. Handles lead storage, imports, and the Instantly.ai integration.

**Stack:** Python 3.12, FastAPI, SQLite, uvicorn, httpx

**Setup:**
```bash
cd gtmbackend
uv sync
uv run python server.py        # starts on http://localhost:8002
```

**Key endpoints:**
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/overview` | DB stats — totals, breakdowns by country, seniority, import, industry |
| `GET` | `/leads` | Paginated leads list (`?page=`, `?search=`, `?country=`) |
| `GET` | `/leads/countries` | Distinct country list with counts |

**Migrations:**
```bash
uv run python migrations/0001_leads.py
uv run python migrations/0002_scoring.py
```

**Instantly.ai service** lives in `services/instantly.py` — wraps the Instantly REST API v2 (campaigns, leads, inbox, analytics). Requires `INSTANTLY_API_KEY` env var.

## gtmfrontend

Next.js 16 + Tailwind v4 dashboard. Two tabs: Overview (DB stats) and Leads (searchable, filterable table).

**Stack:** Next.js 16, React 19, Tailwind v4, @tanstack/react-table, TypeScript

**Setup:**
```bash
cd gtmfrontend
npm install
npm run dev                    # starts on http://localhost:3000
```

Expects the backend at `http://localhost:8002` by default. Override via:
```bash
NEXT_PUBLIC_API_URL=http://localhost:8002 npm run dev
```
or set it in a `.env.local` file.

---

## Other Claude Code GTM references

- https://github.com/sachacoldiq/ColdIQ-s-GTM-Skills
- https://github.com/nimajnebrevilo/GTM-Engine
- https://github.com/kenny589/claude-code-gtm-starter-kit
- https://github.com/growthenginenowoslawski/coldoutboundskills
- https://github.com/ivangfalco/gtm-skills
