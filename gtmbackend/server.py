"""GTM backend — FastAPI server serving leads as HTML."""

from __future__ import annotations

import logging
import logging.handlers
import pathlib

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from db import get_db

logger = logging.getLogger("uvicorn.error")

_LOG_FILE = pathlib.Path(__file__).parent / "server.log"

app = FastAPI(title="GTM Backend")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _setup_file_logging() -> None:
    handler = logging.handlers.RotatingFileHandler(
        _LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root = logging.getLogger()
    root.addHandler(handler)
    if root.level == logging.NOTSET:
        root.setLevel(logging.INFO)


@app.on_event("startup")
def _startup():
    _setup_file_logging()
    logger.info("GTM Backend started  (logging to %s)", _LOG_FILE)


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

_COLS = [
    ("full_name",    "Name"),
    ("title",        "Title"),
    ("seniority",    "Seniority"),
    ("company_name", "Company"),
    ("email",        "Email"),
    ("lead_country", "Country"),
    ("import_name",  "Import"),
    ("created_at",   "Added"),
]


def _escape(val: object) -> str:
    if val is None:
        return ""
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


@app.get("/leads")
def list_leads(
    page: int = 1,
    per_page: int = 50,
    search: str = "",
    country: str = "",
):
    offset = (page - 1) * per_page
    clauses: list[str] = []
    params: list = []
    if search:
        clauses.append("(full_name LIKE ? OR email LIKE ? OR company_name LIKE ? OR title LIKE ?)")
        term = f"%{search}%"
        params += [term, term, term, term]
    if country:
        clauses.append("lead_country LIKE ?")
        params.append(f"%{country}%")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    with get_db() as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM leads {where}", params).fetchone()[0]
        rows = conn.execute(
            f"SELECT {', '.join(c for c, _ in _COLS)}, linkedin_link FROM leads {where} ORDER BY id DESC LIMIT ? OFFSET ?",
            params + [per_page, offset],
        ).fetchall()
    pages = max(1, (total + per_page - 1) // per_page)
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": pages,
        "results": [dict(r) for r in rows],
    }


@app.get("/leads/countries")
def list_countries():
    with get_db() as conn:
        rows = conn.execute(
            "SELECT lead_country, COUNT(*) as count FROM leads "
            "WHERE lead_country IS NOT NULL AND lead_country != '' "
            "GROUP BY lead_country ORDER BY count DESC"
        ).fetchall()
    return [dict(r) for r in rows]


@app.get("/overview")
def overview():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        with_email = conn.execute("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''").fetchone()[0]
        with_linkedin = conn.execute("SELECT COUNT(*) FROM leads WHERE linkedin_link IS NOT NULL AND linkedin_link != ''").fetchone()[0]
        by_country = [dict(r) for r in conn.execute(
            "SELECT COALESCE(NULLIF(lead_country,''), 'Unknown') as label, COUNT(*) as count "
            "FROM leads GROUP BY label ORDER BY count DESC LIMIT 10"
        ).fetchall()]
        by_seniority = [dict(r) for r in conn.execute(
            "SELECT COALESCE(NULLIF(seniority,''), 'Unknown') as label, COUNT(*) as count "
            "FROM leads GROUP BY label ORDER BY count DESC"
        ).fetchall()]
        by_import = [dict(r) for r in conn.execute(
            "SELECT import_name as label, COUNT(*) as count "
            "FROM leads GROUP BY import_name ORDER BY count DESC"
        ).fetchall()]
        by_industry = [dict(r) for r in conn.execute(
            "SELECT COALESCE(NULLIF(industry,''), 'Unknown') as label, COUNT(*) as count "
            "FROM leads GROUP BY label ORDER BY count DESC LIMIT 10"
        ).fetchall()]
    return {
        "total": total,
        "with_email": with_email,
        "with_linkedin": with_linkedin,
        "by_country": by_country,
        "by_seniority": by_seniority,
        "by_import": by_import,
        "by_industry": by_industry,
    }


@app.get("/", response_class=HTMLResponse)
def leads_page():
    with get_db() as conn:
        total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
        rows = conn.execute(
            "SELECT " + ", ".join(c for c, _ in _COLS) + " FROM leads ORDER BY id DESC LIMIT 500"
        ).fetchall()

    col_headers = "".join(f"<th>{label}</th>" for _, label in _COLS)
    data_rows = []
    for row in rows:
        cells = "".join(f"<td>{_escape(row[col])}</td>" for col, _ in _COLS)
        data_rows.append(f"<tr>{cells}</tr>")

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>GTM Leads</title>
  <style>
    body {{ font-family: system-ui, sans-serif; margin: 2rem; color: #1a1a1a; }}
    h1 {{ margin-bottom: 0.25rem; }}
    .count {{ color: #666; font-size: 0.9rem; margin-bottom: 1.5rem; }}
    table {{ border-collapse: collapse; width: 100%; font-size: 0.875rem; }}
    th {{ background: #f4f4f5; text-align: left; padding: 0.5rem 0.75rem;
          border-bottom: 2px solid #e4e4e7; white-space: nowrap; }}
    td {{ padding: 0.45rem 0.75rem; border-bottom: 1px solid #f0f0f0;
          max-width: 280px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }}
    tr:hover td {{ background: #fafafa; }}
  </style>
</head>
<body>
  <h1>GTM Leads</h1>
  <p class="count">{total:,} total &mdash; showing latest 500</p>
  <table>
    <thead><tr>{col_headers}</tr></thead>
    <tbody>{"".join(data_rows)}</tbody>
  </table>
</body>
</html>"""
    return HTMLResponse(content=html)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8002, reload=True)
