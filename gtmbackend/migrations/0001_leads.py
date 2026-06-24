"""Migration: create leads table.

Run:
    python migrations/0001_leads.py
    python migrations/0001_leads.py --rollback
"""

from __future__ import annotations

import argparse
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db import get_db


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def upgrade(conn) -> None:
    if _table_exists(conn, "leads"):
        print("  skip   leads (already exists)", flush=True)
        return

    print("  creating leads ...", end=" ", flush=True)
    conn.execute("""
        CREATE TABLE leads (
            id                    INTEGER PRIMARY KEY,
            import_name           TEXT NOT NULL,
            first_name            TEXT,
            last_name             TEXT,
            full_name             TEXT,
            title                 TEXT,
            headline              TEXT,
            seniority             TEXT,
            email                 TEXT,
            linkedin_link         TEXT UNIQUE,
            is_likely_to_engage   TEXT,
            lead_city             TEXT,
            lead_state            TEXT,
            lead_country          TEXT,
            company_name          TEXT,
            industry              TEXT,
            employee_count        INTEGER,
            departments           TEXT,
            subdepartments        TEXT,
            functions             TEXT,
            company_website       TEXT,
            company_website_short TEXT,
            company_blog_link     TEXT,
            company_twitter_link  TEXT,
            company_facebook_link TEXT,
            company_linkedin_link TEXT,
            company_phone         TEXT,
            created_at            TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads (email)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_company ON leads (company_name)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_leads_country ON leads (lead_country)")
    conn.commit()
    print("done", flush=True)


def downgrade(conn) -> None:
    if not _table_exists(conn, "leads"):
        print("  skip   leads (not present)", flush=True)
        return

    print("  dropping leads ...", end=" ", flush=True)
    conn.execute("DROP TABLE leads")
    conn.commit()
    print("done", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollback", action="store_true")
    args = parser.parse_args()

    with get_db() as conn:
        label = "Downgrade" if args.rollback else "Upgrade"
        print(f"{label}: leads table", flush=True)
        try:
            if args.rollback:
                downgrade(conn)
            else:
                upgrade(conn)
        except Exception as exc:
            conn.rollback()
            print(f"FAILED: {exc}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
