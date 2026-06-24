"""GTM backend — FastAPI server."""

from __future__ import annotations

import csv
import io
import logging
import logging.handlers
import pathlib
import subprocess
import sys
import threading
import uuid
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

from db import get_db
import queries

_ROOT          = pathlib.Path(__file__).parent
_SPECS_DIR     = _ROOT / "specs"
_SCORE_SCRIPT  = _ROOT / "scripts" / "score_leads.py"
_SCRAPE_SCRIPT = _ROOT / "scripts" / "scrape_leads.py"

logger    = logging.getLogger("uvicorn.error")
_LOG_FILE = _ROOT / "server.log"

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
    from migrations import run_all
    run_all()
    logger.info("GTM Backend started  (logging to %s)", _LOG_FILE)


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

@app.get("/leads")
def list_leads(
    page: int = 1, per_page: int = 50,
    search: str = "", country: str = "",
    scraped: str = "", scored: str = "",
):
    with get_db() as conn:
        return queries.get_leads(
            conn, page=page, per_page=per_page,
            search=search, country=country,
            scraped_filter=scraped, scored_filter=scored,
        )


@app.get("/leads/countries")
def list_countries():
    with get_db() as conn:
        return queries.get_countries(conn)


@app.get("/overview")
def overview():
    with get_db() as conn:
        return queries.get_overview(conn)


@app.get("/", response_class=HTMLResponse)
def leads_page():
    with get_db() as conn:
        total, rows = queries.get_leads_html(conn)

    col_headers = "".join(f"<th>{label}</th>" for _, label in queries.LEAD_COLS)
    data_rows = "".join(
        "<tr>" + "".join(f"<td>{_escape(r.get(col))}</td>" for col, _ in queries.LEAD_COLS) + "</tr>"
        for r in rows
    )
    return HTMLResponse(content=f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>GTM Leads</title>
<style>
  body{{font-family:system-ui,sans-serif;margin:2rem;color:#1a1a1a}}
  table{{border-collapse:collapse;width:100%;font-size:.875rem}}
  th{{background:#f4f4f5;text-align:left;padding:.5rem .75rem;border-bottom:2px solid #e4e4e7;white-space:nowrap}}
  td{{padding:.45rem .75rem;border-bottom:1px solid #f0f0f0;max-width:280px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
  tr:hover td{{background:#fafafa}}
</style></head>
<body><h1>GTM Leads</h1>
<p style="color:#666;font-size:.9rem;margin-bottom:1.5rem">{total:,} total &mdash; showing latest 500</p>
<table><thead><tr>{col_headers}</tr></thead><tbody>{data_rows}</tbody></table>
</body></html>""")


def _escape(val: object) -> str:
    if val is None:
        return ""
    return str(val).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------

class _ListCreate(BaseModel):
    name: str
    lead_ids: list[int] = []


class _ListAddEntries(BaseModel):
    lead_ids: list[int]


@app.get("/lists")
def get_lists():
    with get_db() as conn:
        return queries.get_lists(conn)


@app.post("/lists", status_code=201)
def create_list(body: _ListCreate):
    with get_db() as conn:
        return queries.create_list(conn, body.name, body.lead_ids)


@app.get("/lists/{list_id}")
def get_list(list_id: int):
    with get_db() as conn:
        result = queries.get_list(conn, list_id)
    if result is None:
        raise HTTPException(status_code=404, detail="List not found")
    return result


@app.post("/lists/{list_id}/entries", status_code=204)
def add_list_entries(list_id: int, body: _ListAddEntries):
    with get_db() as conn:
        if not queries.list_exists(conn, list_id):
            raise HTTPException(status_code=404, detail="List not found")
        queries.add_list_entries(conn, list_id, body.lead_ids)


@app.delete("/lists/{list_id}/entries/{lead_id}", status_code=204)
def remove_list_entry(list_id: int, lead_id: int):
    with get_db() as conn:
        queries.remove_list_entry(conn, list_id, lead_id)


@app.delete("/lists/{list_id}", status_code=204)
def delete_list(list_id: int):
    with get_db() as conn:
        queries.delete_list(conn, list_id)


@app.get("/lists/{list_id}/export")
def export_list(list_id: int):
    with get_db() as conn:
        name, entries = queries.get_list_for_export(conn, list_id)
    if name is None:
        raise HTTPException(status_code=404, detail="List not found")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=queries.LIST_LEAD_COLS)
    writer.writeheader()
    for row in entries:
        writer.writerow({k: (row.get(k) or "") for k in queries.LIST_LEAD_COLS})
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={name.replace(' ', '_')}.csv"},
    )


# ---------------------------------------------------------------------------
# Scoring — spec management + job runner
# ---------------------------------------------------------------------------

_score_jobs: dict[str, dict] = {}


class _SpecSave(BaseModel):
    name: str
    content: str


class _SpecUpdate(BaseModel):
    content: str


class _ScoringRun(BaseModel):
    spec: str
    list_id: int | None = None
    limit: int | None = None
    all_mode: bool = False


@app.get("/scoring/specs")
def list_specs():
    _SPECS_DIR.mkdir(exist_ok=True)
    return [p.name for p in sorted(_SPECS_DIR.glob("*.yaml"))]


@app.get("/scoring/specs/{name}")
def get_spec(name: str):
    path = _SPECS_DIR / name
    if not path.exists():
        raise HTTPException(404, "Spec not found")
    return {"name": name, "content": path.read_text(encoding="utf-8")}


@app.post("/scoring/specs", status_code=201)
def create_spec(body: _SpecSave):
    _SPECS_DIR.mkdir(exist_ok=True)
    path = _SPECS_DIR / body.name
    if path.exists():
        raise HTTPException(409, "Spec already exists")
    path.write_text(body.content, encoding="utf-8")
    return {"name": body.name}


@app.put("/scoring/specs/{name}")
def update_spec(name: str, body: _SpecUpdate):
    path = _SPECS_DIR / name
    if not path.exists():
        raise HTTPException(404, "Spec not found")
    path.write_text(body.content, encoding="utf-8")
    return {"name": name}


@app.delete("/scoring/specs/{name}", status_code=204)
def delete_spec(name: str):
    path = _SPECS_DIR / name
    if path.exists():
        path.unlink()


@app.post("/scoring/run", status_code=202)
def scoring_run(body: _ScoringRun):
    spec_path = _SPECS_DIR / body.spec
    if not spec_path.exists():
        raise HTTPException(404, "Spec not found")
    if not _SCORE_SCRIPT.exists():
        raise HTTPException(500, f"score_leads.py not found at {_SCORE_SCRIPT}")

    job_id = str(uuid.uuid4())[:8]
    _score_jobs[job_id] = {
        "status": "running", "spec": body.spec, "log": [],
        "started_at": datetime.now().isoformat(),
        "finished_at": None, "exit_code": None,
    }

    def _run() -> None:
        cmd = [sys.executable, str(_SCORE_SCRIPT), "--spec", str(spec_path)]
        if body.list_id:
            cmd += ["--list", str(body.list_id)]
        if body.limit:
            cmd += ["--limit", str(body.limit)]
        if body.all_mode:
            cmd.append("--all")
        _launch(cmd, _score_jobs, job_id)

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}


@app.get("/scoring/job/{job_id}")
def scoring_job(job_id: str):
    job = _score_jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return {**job, "id": job_id}


@app.get("/scoring/leads")
def scoring_leads(page: int = 1, per_page: int = 100, tier: str = ""):
    with get_db() as conn:
        return queries.get_scored_leads(conn, page=page, per_page=per_page, tier=tier)


# ---------------------------------------------------------------------------
# Scraping — job runner
# ---------------------------------------------------------------------------

_scrape_jobs: dict[str, dict] = {}


class _ScrapeRun(BaseModel):
    list_id: int | None = None
    limit: int | None = None
    domain: str | None = None
    all_mode: bool = False
    workers: int = 5


@app.get("/scraping/stats")
def scraping_stats():
    with get_db() as conn:
        return queries.get_scraping_stats(conn)


@app.post("/scraping/run", status_code=202)
def scraping_run(body: _ScrapeRun):
    if not _SCRAPE_SCRIPT.exists():
        raise HTTPException(500, f"scrape_leads.py not found at {_SCRAPE_SCRIPT}")

    job_id = str(uuid.uuid4())[:8]
    _scrape_jobs[job_id] = {
        "status": "running", "log": [],
        "started_at": datetime.now().isoformat(),
        "finished_at": None, "exit_code": None,
    }

    def _run() -> None:
        cmd = [sys.executable, str(_SCRAPE_SCRIPT)]
        if body.list_id:
            cmd += ["--list", str(body.list_id)]
        if body.limit:
            cmd += ["--limit", str(body.limit)]
        if body.domain:
            cmd += ["--domain", body.domain]
        if body.all_mode:
            cmd.append("--all")
        if body.workers != 5:
            cmd += ["--workers", str(body.workers)]
        _launch(cmd, _scrape_jobs, job_id)

    threading.Thread(target=_run, daemon=True).start()
    return {"job_id": job_id}


@app.get("/scraping/job/{job_id}")
def scraping_job(job_id: str):
    job = _scrape_jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "Job not found")
    return {**job, "id": job_id}


# ---------------------------------------------------------------------------
# Shared subprocess launcher
# ---------------------------------------------------------------------------

def _launch(cmd: list[str], jobs: dict, job_id: str) -> None:
    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, cwd=str(_ROOT),
        )
        for line in proc.stdout:  # type: ignore[union-attr]
            jobs[job_id]["log"].append(line.rstrip())
        proc.wait()
        jobs[job_id]["exit_code"] = proc.returncode
    except Exception as exc:
        jobs[job_id]["log"].append(f"[launcher error] {exc}")
        jobs[job_id]["exit_code"] = -1
    finally:
        jobs[job_id]["status"] = "done"
        jobs[job_id]["finished_at"] = datetime.now().isoformat()


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8002, reload=True)
