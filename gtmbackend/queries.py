"""All database queries for the GTM backend.

Every function receives an open sqlite3 connection and returns plain Python
objects (dicts / lists). No FastAPI types here.
"""

from __future__ import annotations

import re

# ── Columns returned on the /leads list ──────────────────────────────────────

LEAD_COLS = [
    ("full_name",    "Name"),
    ("title",        "Title"),
    ("seniority",    "Seniority"),
    ("company_name", "Company"),
    ("email",        "Email"),
    ("lead_country", "Country"),
    ("import_name",  "Import"),
    ("created_at",   "Added"),
]

LIST_LEAD_COLS = ["id", "full_name", "title", "email", "company_name", "lead_country", "seniority"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def normalize_domain(url: str | None) -> str | None:
    if not url:
        return None
    s = url.strip()
    s = re.sub(r"^https?://", "", s, flags=re.I)
    s = re.sub(r"^www\.", "", s, flags=re.I)
    return s.rstrip("/").split("?")[0].split("#")[0].split("/")[0].lower() or None


def scraped_clause(conn, want_scraped: bool) -> tuple[str, list]:
    """Return (sql_clause, params) filtering by scraped status."""
    all_urls = conn.execute(
        "SELECT DISTINCT company_website_short FROM leads "
        "WHERE company_website_short IS NOT NULL AND company_website_short != ''"
    ).fetchall()
    scraped_domains = {
        row["domain"] for row in conn.execute(
            "SELECT domain FROM scraped_pages WHERE text IS NOT NULL"
        ).fetchall()
    }
    matching = [
        row["company_website_short"] for row in all_urls
        if normalize_domain(row["company_website_short"]) in scraped_domains
    ]
    if want_scraped:
        if not matching:
            return ("1=0", [])
        ph = ",".join("?" * len(matching))
        return (f"company_website_short IN ({ph})", matching)
    else:
        if not matching:
            return ("1=1", [])
        ph = ",".join("?" * len(matching))
        return (
            f"(company_website_short IS NULL OR company_website_short = '' "
            f"OR company_website_short NOT IN ({ph}))",
            matching,
        )


# ── Leads ─────────────────────────────────────────────────────────────────────

def get_leads(
    conn, *, page: int, per_page: int,
    search: str, country: str, scraped_filter: str, scored_filter: str,
) -> dict:
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
    if scored_filter == "yes":
        clauses.append("scored_at IS NOT NULL")
    elif scored_filter == "no":
        clauses.append("scored_at IS NULL")
    if scraped_filter in ("yes", "no"):
        sc_clause, sc_params = scraped_clause(conn, scraped_filter == "yes")
        clauses.append(sc_clause)
        params.extend(sc_params)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    col_list = ", ".join(c for c, _ in LEAD_COLS)

    total = conn.execute(f"SELECT COUNT(*) FROM leads {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT id, {col_list}, linkedin_link, fit_score, tier, company_website_short "
        f"FROM leads {where} ORDER BY id DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()

    # Batch-check scraped status for the display column
    domains = list({d for r in rows if (d := normalize_domain(r["company_website_short"]))})
    if domains:
        ph = ",".join("?" * len(domains))
        scraped_set = {
            row["domain"] for row in conn.execute(
                f"SELECT domain FROM scraped_pages WHERE text IS NOT NULL AND domain IN ({ph})",
                domains,
            ).fetchall()
        }
    else:
        scraped_set = set()

    results = []
    for r in rows:
        d = dict(r)
        domain = normalize_domain(d.pop("company_website_short", None))
        d["scraped"] = domain in scraped_set if domain else False
        results.append(d)

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "pages": max(1, (total + per_page - 1) // per_page),
        "results": results,
    }


def get_countries(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT lead_country, COUNT(*) as count FROM leads "
        "WHERE lead_country IS NOT NULL AND lead_country != '' "
        "GROUP BY lead_country ORDER BY count DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_overview(conn) -> dict:
    total        = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    with_email   = conn.execute("SELECT COUNT(*) FROM leads WHERE email IS NOT NULL AND email != ''").fetchone()[0]
    with_linkedin = conn.execute("SELECT COUNT(*) FROM leads WHERE linkedin_link IS NOT NULL AND linkedin_link != ''").fetchone()[0]
    by_country   = [dict(r) for r in conn.execute(
        "SELECT COALESCE(NULLIF(lead_country,''), 'Unknown') as label, COUNT(*) as count "
        "FROM leads GROUP BY label ORDER BY count DESC LIMIT 10"
    ).fetchall()]
    by_seniority = [dict(r) for r in conn.execute(
        "SELECT COALESCE(NULLIF(seniority,''), 'Unknown') as label, COUNT(*) as count "
        "FROM leads GROUP BY label ORDER BY count DESC"
    ).fetchall()]
    by_import    = [dict(r) for r in conn.execute(
        "SELECT import_name as label, COUNT(*) as count FROM leads GROUP BY import_name ORDER BY count DESC"
    ).fetchall()]
    by_industry  = [dict(r) for r in conn.execute(
        "SELECT COALESCE(NULLIF(industry,''), 'Unknown') as label, COUNT(*) as count "
        "FROM leads GROUP BY label ORDER BY count DESC LIMIT 10"
    ).fetchall()]
    return {
        "total": total, "with_email": with_email, "with_linkedin": with_linkedin,
        "by_country": by_country, "by_seniority": by_seniority,
        "by_import": by_import, "by_industry": by_industry,
    }


def get_leads_html(conn) -> tuple[int, list[dict]]:
    """Return (total, rows) for the HTML page."""
    total = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    col_list = ", ".join(c for c, _ in LEAD_COLS)
    rows = conn.execute(
        f"SELECT {col_list} FROM leads ORDER BY id DESC LIMIT 500"
    ).fetchall()
    return total, [dict(r) for r in rows]


# ── Lists ─────────────────────────────────────────────────────────────────────

def get_lists(conn) -> list[dict]:
    rows = conn.execute(
        "SELECT l.id, l.name, l.created_at, COUNT(e.id) as entry_count "
        "FROM lists l LEFT JOIN list_entries e ON l.id = e.list_id "
        "GROUP BY l.id ORDER BY l.created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]


def create_list(conn, name: str, lead_ids: list[int]) -> dict:
    row = conn.execute(
        "INSERT INTO lists (name) VALUES (?) RETURNING id, name, created_at", (name,)
    ).fetchone()
    list_id = row["id"]
    for lead_id in lead_ids:
        conn.execute(
            "INSERT OR IGNORE INTO list_entries (list_id, lead_id) VALUES (?, ?)",
            (list_id, lead_id),
        )
    conn.commit()
    return dict(row) | {"entry_count": len(lead_ids)}


def get_list(conn, list_id: int) -> dict | None:
    lst = conn.execute(
        "SELECT id, name, created_at FROM lists WHERE id = ?", (list_id,)
    ).fetchone()
    if lst is None:
        return None
    col_list = ", ".join(f"l.{c}" for c in LIST_LEAD_COLS)
    entries = conn.execute(
        f"SELECT {col_list} FROM list_entries e JOIN leads l ON e.lead_id = l.id "
        "WHERE e.list_id = ? ORDER BY e.added_at ASC",
        (list_id,),
    ).fetchall()
    return dict(lst) | {"entries": [dict(e) for e in entries]}


def list_exists(conn, list_id: int) -> bool:
    return conn.execute("SELECT id FROM lists WHERE id = ?", (list_id,)).fetchone() is not None


def add_list_entries(conn, list_id: int, lead_ids: list[int]) -> None:
    for lead_id in lead_ids:
        conn.execute(
            "INSERT OR IGNORE INTO list_entries (list_id, lead_id) VALUES (?, ?)",
            (list_id, lead_id),
        )
    conn.commit()


def remove_list_entry(conn, list_id: int, lead_id: int) -> None:
    conn.execute(
        "DELETE FROM list_entries WHERE list_id = ? AND lead_id = ?", (list_id, lead_id)
    )
    conn.commit()


def delete_list(conn, list_id: int) -> None:
    conn.execute("DELETE FROM lists WHERE id = ?", (list_id,))
    conn.commit()


def get_list_for_export(conn, list_id: int) -> tuple[str | None, list[dict]]:
    """Return (list_name, entries) or (None, []) if not found."""
    lst = conn.execute("SELECT name FROM lists WHERE id = ?", (list_id,)).fetchone()
    if lst is None:
        return None, []
    col_list = ", ".join(f"l.{c}" for c in LIST_LEAD_COLS)
    entries = conn.execute(
        f"SELECT {col_list} FROM list_entries e JOIN leads l ON e.lead_id = l.id "
        "WHERE e.list_id = ? ORDER BY e.added_at ASC",
        (list_id,),
    ).fetchall()
    return lst["name"], [dict(e) for e in entries]


# ── Scoring ───────────────────────────────────────────────────────────────────

def get_scored_leads(conn, *, page: int, per_page: int, tier: str) -> dict:
    offset = (page - 1) * per_page
    clauses = ["scored_at IS NOT NULL"]
    params: list = []
    if tier:
        clauses.append("tier = ?")
        params.append(tier)
    where = "WHERE " + " AND ".join(clauses)
    total = conn.execute(f"SELECT COUNT(*) FROM leads {where}", params).fetchone()[0]
    rows = conn.execute(
        f"SELECT id, full_name, title, company_name, lead_country, "
        f"fit_score, tier, confidence, disqualified, disqualifier, score_reason, scored_at "
        f"FROM leads {where} ORDER BY fit_score DESC LIMIT ? OFFSET ?",
        params + [per_page, offset],
    ).fetchall()
    return {
        "total": total, "page": page,
        "pages": max(1, (total + per_page - 1) // per_page),
        "results": [dict(r) for r in rows],
    }


# ── Scraping ──────────────────────────────────────────────────────────────────

def get_scraping_stats(conn) -> dict:
    total_leads     = conn.execute("SELECT COUNT(*) FROM leads").fetchone()[0]
    unique_domains  = conn.execute(
        "SELECT COUNT(DISTINCT company_website_short) FROM leads "
        "WHERE company_website_short IS NOT NULL AND company_website_short != ''"
    ).fetchone()[0]
    scraped_ok      = conn.execute(
        "SELECT COUNT(*) FROM scraped_pages WHERE text IS NOT NULL"
    ).fetchone()[0]
    scraped_failed  = conn.execute(
        "SELECT COUNT(*) FROM scraped_pages WHERE text IS NULL AND scrape_error IS NOT NULL"
    ).fetchone()[0]
    return {
        "total_leads": total_leads,
        "unique_domains": unique_domains,
        "scraped_ok": scraped_ok,
        "scraped_failed": scraped_failed,
    }
