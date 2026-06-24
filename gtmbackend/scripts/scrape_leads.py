"""Scrape company websites and save plain-text content to scraped/<slug>.txt.

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

import httpx
from bs4 import BeautifulSoup

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
from db import get_db

_SCRAPED_DIR = pathlib.Path(__file__).parent.parent / "scraped"

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


def url_to_slug(url: str) -> str:
    """Convert a URL to a filesystem-safe slug used as the scraped filename stem."""
    s = url.strip()
    s = re.sub(r"^https?://", "", s, flags=re.I)
    s = re.sub(r"^www\.", "", s, flags=re.I)
    s = s.rstrip("/").split("?")[0].split("#")[0]
    return s.replace("/", "_").replace(".", "_")


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


def scrape(url: str) -> tuple[str, str | None]:
    """Return (slug, text) or (slug, None) on failure."""
    slug = url_to_slug(url)
    try:
        client = httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True, verify=False)
        resp = client.get(f"https://{url}" if not url.startswith("http") else url)
        resp.raise_for_status()
        final_url = str(resp.url)
        homepage_html = resp.text
        parts = [_extract_text(homepage_html)]

        for inner in _inner_signal_links(homepage_html, final_url):
            try:
                r = client.get(inner)
                if r.status_code == 200:
                    parts.append(_extract_text(r.text))
            except Exception:
                pass

        client.close()
        return slug, "\n\n---\n\n".join(p for p in parts if p.strip())
    except Exception as exc:
        return slug, None


def _get_domains(all_mode: bool, domain_filter: str | None) -> list[tuple[str, str]]:
    """Return list of (url, slug) to scrape from the leads DB."""
    with get_db() as conn:
        rows = conn.execute(
            "SELECT DISTINCT company_name, company_website_short "
            "FROM leads WHERE company_website_short IS NOT NULL AND company_website_short != ''"
        ).fetchall()

    pairs: list[tuple[str, str]] = []
    seen: set[str] = set()
    for row in rows:
        url = row["company_website_short"].strip()
        slug = url_to_slug(url)
        if slug in seen:
            continue
        seen.add(slug)

        if domain_filter and domain_filter.lower() not in url.lower():
            continue

        if not all_mode and (_SCRAPED_DIR / f"{slug}.txt").exists():
            continue

        pairs.append((url, slug))

    return pairs


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape company websites into scraped/*.txt")
    parser.add_argument("--limit", type=int, metavar="N")
    parser.add_argument("--domain", metavar="DOMAIN", help="Filter to this domain only")
    parser.add_argument("--all", dest="all_mode", action="store_true", help="Re-scrape already-scraped")
    parser.add_argument("--workers", type=int, default=5, metavar="N")
    args = parser.parse_args()

    _SCRAPED_DIR.mkdir(exist_ok=True)

    pairs = _get_domains(args.all_mode, args.domain)
    if args.limit:
        pairs = pairs[: args.limit]

    if not pairs:
        print("Nothing to scrape.")
        return

    already = sum(1 for _ in _SCRAPED_DIR.glob("*.txt"))
    print(f"Scraping {len(pairs)} company websites  (already have {already})")

    ok = failed = 0

    def _worker(item: tuple[str, str]) -> tuple[str, str, str | None]:
        url, slug = item
        _, text = scrape(url)
        return url, slug, text

    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(_worker, p): p for p in pairs}
        for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
            url, slug, text = future.result()
            pct = i / len(pairs) * 100
            if text:
                (_SCRAPED_DIR / f"{slug}.txt").write_text(text, encoding="utf-8")
                print(f"[{i}/{len(pairs)}] {pct:5.1f}%  OK    {url}", flush=True)
                ok += 1
            else:
                print(f"[{i}/{len(pairs)}] {pct:5.1f}%  FAIL  {url}", flush=True)
                failed += 1

    print(f"\nDone. {ok} OK, {failed} failed. Files in {_SCRAPED_DIR}")


if __name__ == "__main__":
    main()
