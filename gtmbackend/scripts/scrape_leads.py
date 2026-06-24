"""Scrape company websites and store plain-text content in the scraped_pages table.

Usage:
    uv run scripts/scrape_leads.py              # scrape all unscraped companies
    uv run scripts/scrape_leads.py --limit 50   # cap at 50
    uv run scripts/scrape_leads.py --domain example.com   # single domain
    uv run scripts/scrape_leads.py --all        # re-scrape everything
    uv run scripts/scrape_leads.py --workers 10 # concurrent HTTP workers (default 5)
"""

from __future__ import annotations

import argparse
import concurrent.futures
import pathlib
import re
import sys
import threading
from datetime import datetime, timezone

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db import get_db

_SIGNAL_PATHS = (
    "/about", "/about-us",
    "/pricing", "/plans",
    "/services", "/service",
    "/products", "/features",
    "/solutions",
    "/contact",
)

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; gtmbackend-scraper/1.0)"}
_TIMEOUT = httpx.Timeout(connect=8.0, read=12.0, write=5.0, pool=5.0)
_HTML_CAP = 400_000

# Serialize SQLite writes across threads
_db_lock = threading.Lock()


def _normalize_domain(url: str) -> str:
    s = url.strip()
    s = re.sub(r"^https?://", "", s, flags=re.I)
    s = re.sub(r"^www\.", "", s, flags=re.I)
    return s.rstrip("/").split("?")[0].split("#")[0].split("/")[0].lower()


def _extract_text(html: str) -> str:
    soup = BeautifulSoup(html[:_HTML_CAP], "html.parser")
    for tag in soup(["script", "style", "noscript", "head", "meta"]):
        tag.decompose()
    return re.sub(r"\s{2,}", " ", soup.get_text(separator=" ", strip=True))[:8000]


def _inner_signal_links(html: str, base_url: str) -> list[str]:
    from urllib.parse import urljoin, urlparse
    base_host = urlparse(base_url).netloc
    soup = BeautifulSoup(html[:_HTML_CAP], "html.parser")
    seen: set[str] = set()
    found: list[str] = []
    for a in soup.find_all("a", href=True):
        href = str(a["href"]).strip()
        full = urljoin(base_url, href).split("?")[0].split("#")[0]
        parsed = urlparse(full)
        if parsed.netloc != base_host:
            continue
        path = parsed.path.rstrip("/").lower() or "/"
        if path in seen:
            continue
        for signal in _SIGNAL_PATHS:
            if path == signal or path.startswith(signal + "/"):
                seen.add(path)
                found.append(full)
                break
    return found[:5]


def _scrape_url(url: str) -> tuple[str, str, int]:
    """Fetch pages for url. Returns (final_url, text, pages_scraped) or raises."""
    client = httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True, verify=False)
    resp = client.get(f"https://{url}" if not url.startswith("http") else url)
    resp.raise_for_status()
    final_url = str(resp.url)
    homepage_html = resp.text
    parts = [_extract_text(homepage_html)]
    pages = 1

    for inner in _inner_signal_links(homepage_html, final_url):
        try:
            r = client.get(inner)
            if r.status_code == 200:
                parts.append(_extract_text(r.text))
                pages += 1
        except Exception:
            pass

    client.close()
    text = "\n\n---\n\n".join(p for p in parts if p.strip())
    return final_url, text, pages


def _get_list_lead_websites(list_id: int) -> list[str]:
    """Return company_website_short values for all leads in a list."""
    with get_db() as conn:
        list_row = conn.execute("SELECT name FROM lists WHERE id = ?", (list_id,)).fetchone()
        if list_row is None:
            print(f"List {list_id} not found.", file=sys.stderr)
            sys.exit(1)
        rows = conn.execute(
            "SELECT DISTINCT l.company_website_short FROM list_entries le "
            "JOIN leads l ON le.lead_id = l.id "
            "WHERE le.list_id = ? AND l.company_website_short IS NOT NULL AND l.company_website_short != ''",
            (list_id,),
        ).fetchall()
    print(f"List: {list_row['name']} ({len(rows)} unique websites)", flush=True)
    return [row["company_website_short"] for row in rows]


def _get_targets(all_mode: bool, domain_filter: str | None, list_id: int | None = None) -> list[tuple[str, str]]:
    """Return list of (raw_url, domain) to scrape."""
    with get_db() as conn:
        if list_id is not None:
            websites = _get_list_lead_websites(list_id)
            rows = [{"company_website_short": w} for w in websites]
        else:
            rows = conn.execute(
                "SELECT DISTINCT company_website_short FROM leads "
                "WHERE company_website_short IS NOT NULL AND company_website_short != ''"
            ).fetchall()

    targets: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        raw_url = row["company_website_short"].strip()
        domain = _normalize_domain(raw_url)
        if not domain or domain in seen:
            continue
        seen.add(domain)

        if domain_filter and domain_filter.lower() not in domain.lower():
            continue

        targets.append((raw_url, domain))

    if all_mode or not targets:
        return targets

    # Filter out domains already successfully scraped
    domains = [d for _, d in targets]
    placeholders = ",".join("?" * len(domains))
    with get_db() as conn:
        already = {
            row["domain"]
            for row in conn.execute(
                f"SELECT domain FROM scraped_pages WHERE domain IN ({placeholders}) AND text IS NOT NULL",
                domains,
            ).fetchall()
        }

    return [(url, d) for url, d in targets if d not in already]


def _save(domain: str, final_url: str, text: str, pages: int) -> None:
    with _db_lock:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO scraped_pages (domain, final_url, text, pages_scraped, scraped_at, scrape_error, failed_at)
                   VALUES (?, ?, ?, ?, ?, NULL, NULL)
                   ON CONFLICT(domain) DO UPDATE SET
                       final_url=excluded.final_url, text=excluded.text,
                       pages_scraped=excluded.pages_scraped, scraped_at=excluded.scraped_at,
                       scrape_error=NULL, failed_at=NULL""",
                (domain, final_url, text, pages, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()


def _save_error(domain: str, error: str) -> None:
    with _db_lock:
        with get_db() as conn:
            conn.execute(
                """INSERT INTO scraped_pages (domain, scrape_error, failed_at)
                   VALUES (?, ?, ?)
                   ON CONFLICT(domain) DO UPDATE SET
                       scrape_error=excluded.scrape_error, failed_at=excluded.failed_at
                   WHERE scraped_pages.text IS NULL""",
                (domain, error, datetime.now(timezone.utc).isoformat()),
            )
            conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape company websites into scraped_pages table")
    parser.add_argument("--list", dest="list_id", type=int, metavar="LIST_ID",
                        help="Only scrape companies from leads in this list")
    parser.add_argument("--limit", type=int, metavar="N")
    parser.add_argument("--domain", metavar="DOMAIN", help="Filter to this domain only")
    parser.add_argument("--all", dest="all_mode", action="store_true", help="Re-scrape already-scraped")
    parser.add_argument("--workers", type=int, default=5, metavar="N")
    args = parser.parse_args()

    targets = _get_targets(args.all_mode, args.domain, args.list_id)
    if args.limit:
        targets = targets[: args.limit]

    if not targets:
        print("Nothing to scrape.")
        return

    with get_db() as conn:
        already = conn.execute("SELECT COUNT(*) FROM scraped_pages WHERE text IS NOT NULL").fetchone()[0]
    print(f"To scrape: {len(targets)}  (already in DB: {already})", flush=True)

    ok = failed = 0

    def _worker(item: tuple[str, str]) -> tuple[str, str, str | None, str | None, int]:
        raw_url, domain = item
        try:
            final_url, text, pages = _scrape_url(raw_url)
            return domain, final_url, text, None, pages
        except Exception as exc:
            return domain, raw_url, None, f"{type(exc).__name__}: {exc}", 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_worker, t): t for t in targets}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            domain, final_url, text, error, pages = future.result()
            pct = i / len(targets) * 100
            if text:
                _save(domain, final_url, text, pages)
                print(f"[{i}/{len(targets)}] {pct:5.1f}%  OK    {domain}  ({pages}p)", flush=True)
                ok += 1
            else:
                _save_error(domain, error or "unknown error")
                print(f"[{i}/{len(targets)}] {pct:5.1f}%  FAIL  {domain}  {error}", flush=True)
                failed += 1

    print(f"\nDone. {ok} OK, {failed} failed.", flush=True)


if __name__ == "__main__":
    main()
