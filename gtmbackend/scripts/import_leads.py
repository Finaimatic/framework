"""Import a leadsexport CSV into the leads table.

Usage:
    python scripts/import_leads.py path/to/file.csv
    python scripts/import_leads.py path/to/file.csv --import-name "B2B high growth"
"""

from __future__ import annotations

import argparse
import csv
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db import get_db


def _parse_int(val: str) -> int | None:
    try:
        return int(val.replace(",", "").strip())
    except (ValueError, AttributeError):
        return None


def import_csv(path: pathlib.Path, import_name: str) -> None:
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    inserted = skipped = 0

    with get_db() as conn:
        for row in rows:
            linkedin = row.get("LinkedIn Link", "").strip() or None
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO leads (
                        import_name, first_name, last_name, full_name,
                        title, headline, seniority, email, linkedin_link,
                        is_likely_to_engage,
                        lead_city, lead_state, lead_country,
                        company_name, industry, employee_count,
                        departments, subdepartments, functions,
                        company_website, company_website_short,
                        company_blog_link, company_twitter_link,
                        company_facebook_link, company_linkedin_link,
                        company_phone
                    ) VALUES (
                        ?, ?, ?, ?,
                        ?, ?, ?, ?, ?,
                        ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?, ?,
                        ?, ?,
                        ?, ?,
                        ?, ?,
                        ?
                    )
                    """,
                    (
                        import_name,
                        row.get("First Name", "").strip() or None,
                        row.get("Last Name", "").strip() or None,
                        row.get("Full Name", "").strip() or None,
                        row.get("Title", "").strip() or None,
                        row.get("Headline", "").strip() or None,
                        row.get("Seniority", "").strip() or None,
                        row.get("Email", "").strip() or None,
                        linkedin,
                        row.get("Is Likely To Engage", "").strip() or None,
                        row.get("Lead City", "").strip() or None,
                        row.get("Lead State", "").strip() or None,
                        row.get("Lead Country", "").strip() or None,
                        row.get("Company Name", "").strip() or None,
                        row.get("Industry", "").strip() or None,
                        _parse_int(row.get("Employee Count", "")),
                        row.get("Departments", "").strip() or None,
                        row.get("Subdepartments", "").strip() or None,
                        row.get("Functions", "").strip() or None,
                        row.get("Company Website Full", "").strip() or None,
                        row.get("Company Website Short", "").strip() or None,
                        row.get("Company Blog Link", "").strip() or None,
                        row.get("Company Twitter Link", "").strip() or None,
                        row.get("Company Facebook Link", "").strip() or None,
                        row.get("Company LinkedIn Link", "").strip() or None,
                        row.get("Company Phone Number", "").strip() or None,
                    ),
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
                else:
                    skipped += 1
            except Exception as exc:
                print(f"  error on row {row.get('Full Name')}: {exc}", file=sys.stderr)

        conn.commit()

    total = len(rows)
    print(f"Done: {inserted} inserted, {skipped} skipped (duplicates) out of {total} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import a leadsexport CSV into leads table")
    parser.add_argument("file", type=pathlib.Path, help="Path to CSV file")
    parser.add_argument(
        "--import-name",
        help="Label for this import batch (default: CSV filename without extension)",
    )
    args = parser.parse_args()

    if not args.file.exists():
        print(f"File not found: {args.file}", file=sys.stderr)
        sys.exit(1)

    import_name = args.import_name or args.file.stem
    print(f"Importing '{args.file.name}' as '{import_name}' ...")
    import_csv(args.file, import_name)


if __name__ == "__main__":
    main()
