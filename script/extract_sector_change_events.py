"""Convert archived NSE reconstitution-notice text into auditable sector events.

The output is deliberately a *candidate* ledger.  Every row retains the source
notice and section so validation can reject malformed or ambiguous extractions
before it is used by the point-in-time universe reconstructor.
"""

import argparse
import csv
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/universe/source/sector_reconstitution_notices"
DEFAULT_OUTPUT = ROOT / "data/universe/sector_changes_candidates.csv"

LOCAL_UNIVERSES = {
    "NIFTY AUTO": "NIFTY_AUTO", "NIFTY BANK": "NIFTY_BANK",
    "NIFTY CAPITAL GOODS": "NIFTY_CAPITAL_GOODS", "NIFTY CEMENT": "NIFTY_CEMENT",
    "NIFTY CHEMICALS": "NIFTY_CHEMICALS", "NIFTY COMMERCIAL AND TRANSPORT SERVICES": "NIFTY_COMMERCIAL_TRANSPORT_SERVICES",
    "NIFTY CONSUMER DURABLES": "NIFTY_CONSUMER_DURABLES", "NIFTY CONSUMER SERVICES": "NIFTY_CONSUMER_SERVICES",
    "NIFTY FINANCIAL SERVICES": "NIFTY_FINANCIAL_SERVICES", "NIFTY FINANCIAL SERVICES 25/50": "NIFTY_FINANCIAL_SERVICES_25_50",
    "NIFTY FINANCIAL SERVICES EX-BANK": "NIFTY_FINANCIAL_SERVICES_EX_BANK", "NIFTY FMCG": "NIFTY_FMCG",
    "NIFTY HEALTHCARE": "NIFTY_HEALTHCARE", "NIFTY HEALTHCARE INDEX": "NIFTY_HEALTHCARE",
    "NIFTY HOSPITALS": "NIFTY_HOSPITALS", "NIFTY HOUSING FINANCE": "NIFTY_HOUSING_FINANCE",
    "NIFTY INSURANCE": "NIFTY_INSURANCE", "NIFTY IT": "NIFTY_IT", "NIFTY MEDIA": "NIFTY_MEDIA",
    "NIFTY METAL": "NIFTY_METAL", "NIFTY NBFC": "NIFTY_NBFC", "NIFTY OIL & GAS": "NIFTY_OIL_GAS",
    "NIFTY OIL AND GAS": "NIFTY_OIL_GAS", "NIFTY PHARMA": "NIFTY_PHARMA", "NIFTY POWER": "NIFTY_POWER",
    "NIFTY PRIVATE BANK": "NIFTY_PRIVATE_BANK", "NIFTY PSU BANK": "NIFTY_PSU_BANK",
    "NIFTY REALTY": "NIFTY_REALTY", "NIFTY RETAIL": "NIFTY_RETAIL",
    "NIFTY TELECOMMUNICATIONS": "NIFTY_TELECOMMUNICATIONS", "NIFTY MIDS MALL FINANCIAL SERVICES": "NIFTY_MIDSMALL_FINANCIAL_SERVICES",
    "NIFTY MIDSMALL FINANCIAL SERVICES": "NIFTY_MIDSMALL_FINANCIAL_SERVICES",
    "NIFTY MIDSMALL HEALTHCARE": "NIFTY_MIDSMALL_HEALTHCARE", "NIFTY MIDSMALL IT AND TELECOM": "NIFTY_MIDSMALL_IT_TELECOM",
}
HEADING_RE = re.compile(r"(?mi)^\s*(?:\d+|[a-z])\)\s+(NIFTY[^\n]+?)\s*$")
SYMBOL_RE = re.compile(r"^\s*\d+\s+.*?\s+([A-Z][A-Z0-9&-]{1,})\s*$")
DATE_RE = re.compile(r"(?:effective|w\.e\.f\.?)[^\n]{0,100}?([A-Z][a-z]+\s+\d{1,2},?\s+20\d{2})", re.I)


def normalise_heading(value: str) -> str:
    value = re.sub(r"\s+", " ", value.upper()).strip().replace("&", " AND ")
    value = re.sub(r"\s+", " ", value).replace("NIFTY MIDS MALL", "NIFTY MIDSMALL")
    return value


def effective_date(text: str) -> str | None:
    match = DATE_RE.search(text[:2000])
    if not match:
        return None
    value = match.group(1).replace(",", "")
    try:
        return str(__import__("datetime").datetime.strptime(value, "%B %d %Y").date())
    except ValueError:
        return None


def extract_section_events(section: str):
    mode = None
    events = []
    for line in section.splitlines():
        lower = line.lower()
        if "being excluded" in lower or "are excluded" in lower:
            mode = "REMOVE"
            continue
        if "being included" in lower or "are included" in lower:
            mode = "ADD"
            continue
        if mode:
            match = SYMBOL_RE.match(line)
            if match:
                events.append((mode, match.group(1)))
    return events


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=SOURCE / "manifest.csv")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    rows = []
    with args.manifest.open(newline="", encoding="utf-8") as handle:
        for notice in csv.DictReader(handle):
            text = Path(notice["text_file"]).read_text(encoding="utf-8", errors="replace")
            date = effective_date(text)
            if not date:
                continue
            headings = list(HEADING_RE.finditer(text))
            for position, heading in enumerate(headings):
                source_name = normalise_heading(heading.group(1))
                universe = LOCAL_UNIVERSES.get(source_name)
                if not universe:
                    continue
                end = headings[position + 1].start() if position + 1 < len(headings) else len(text)
                section = text[heading.end():end]
                for action, symbol in extract_section_events(section):
                    rows.append({
                        "universe": universe, "effective_date": date, "action": action, "symbol": symbol,
                        "source_url": notice["url"], "source_file": notice["text_file"],
                        "source_section": heading.group(1).strip(), "review_status": "PENDING_VALIDATION",
                    })
    rows.sort(key=lambda row: (row["effective_date"], row["universe"], row["action"], row["symbol"]))
    fields = ["universe", "effective_date", "action", "symbol", "source_url", "source_file", "source_section", "review_status"]
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} candidate events to {args.output}")


if __name__ == "__main__":
    main()
