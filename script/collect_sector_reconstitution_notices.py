"""Download official NSE Indices reconstitution notices for sector-log extraction.

This intentionally preserves every source PDF and its extracted text.  The notices
often include multiple indices and use slightly different table layouts, so event
normalisation is a separate, auditable step rather than a brittle web scrape.
"""

import argparse
import csv
import html
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

from pypdf import PdfReader


ARCHIVE_URL = "https://www.niftyindices.com/press-release"
BASE_URL = "https://www.niftyindices.com"
LINK_RE = re.compile(
    r'<div class="pressItem" data-date="([^"]+)".*?<a href=\'([^\']+\.pdf)\'[^>]*>(.*?)</a>',
    re.DOTALL,
)
IN_SCOPE = re.compile(r"replacement|reconstitution|change in indices|inclusion|exclusion", re.I)
OUT_OF_SCOPE = re.compile(r"fixed income|10 year|SME|bond|g-sec|bharat bond|reference rate|nifty ipo", re.I)


def fetch(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=60) as response:
        return response.read()


def notices(start_year: int, end_year: int):
    page = fetch(ARCHIVE_URL).decode("utf-8", errors="replace")
    for raw_date, relative_url, raw_title in LINK_RE.findall(page):
        published = datetime.strptime(raw_date, "%b %d, %Y").date()
        title = html.unescape(re.sub(r"<.*?>", "", raw_title)).strip()
        if not (start_year <= published.year <= end_year):
            continue
        if not IN_SCOPE.search(title) or OUT_OF_SCOPE.search(title):
            continue
        yield published, title, f"{BASE_URL}{relative_url}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--start-year", type=int, default=2020)
    parser.add_argument("--end-year", type=int, default=datetime.now().year)
    parser.add_argument("--output", type=Path, default=Path("data/universe/source/sector_reconstitution_notices"))
    parser.add_argument("--limit", type=int, help="Download only the first N notices, for a smoke test")
    args = parser.parse_args()

    output = args.output
    pdf_dir = output / "pdf"
    text_dir = output / "text"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    text_dir.mkdir(parents=True, exist_ok=True)
    selected = sorted(notices(args.start_year, args.end_year), reverse=True)
    if args.limit:
        selected = selected[: args.limit]

    rows = []
    for position, (published, title, url) in enumerate(selected, start=1):
        stem = f"{published.isoformat()}_{Path(url).stem}"
        pdf_file = pdf_dir / f"{stem}.pdf"
        text_file = text_dir / f"{stem}.txt"
        status = "cached" if pdf_file.exists() else "downloaded"
        if not pdf_file.exists():
            pdf_file.write_bytes(fetch(url))
            time.sleep(0.15)
        try:
            extracted = "\n".join(page.extract_text() or "" for page in PdfReader(pdf_file).pages)
            text_file.write_text(extracted, encoding="utf-8")
            status += ":text_ok"
        except Exception as error:  # Source is retained even if text extraction fails.
            status += f":text_error:{type(error).__name__}"
        rows.append({
            "published_date": published.isoformat(),
            "title": title,
            "url": url,
            "pdf_file": str(pdf_file),
            "text_file": str(text_file),
            "status": status,
        })
        print(f"[{position}/{len(selected)}] {published} {title} ({status})")

    with (output / "manifest.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys() if rows else ["published_date", "title", "url", "pdf_file", "text_file", "status"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Collected {len(rows)} notices in {output}")


if __name__ == "__main__":
    main()
