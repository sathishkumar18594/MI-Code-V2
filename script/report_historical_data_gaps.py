import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.universe_service import UniverseService


VERIFIED_ACTIONS = {
    "AMTEKAUTO": {"reason": "Successor mapping supplied by user.", "successor": "REVENT", "evidence_url": None},
    "ALSTOMT&D": {
        "reason": "Renamed from Alstom T&D India Limited to GE Vernova T&D India Limited.",
        "successor": "GETD",
        "evidence_url": None,
    },
    "ARE&M": {"reason": "No replacement; excluded from historical downloader by strategy decision.", "successor": None, "evidence_url": None},
    "ARE& M": {"reason": "No replacement; excluded from historical downloader by strategy decision.", "successor": None, "evidence_url": None},
    "COX&KINGS": {"reason": "No replacement; excluded from historical downloader by strategy decision.", "successor": None, "evidence_url": None},
    "GSKCONS": {"reason": "No replacement; excluded from historical downloader by strategy decision.", "successor": None, "evidence_url": None},
    "GUJNRECOKE": {"reason": "No replacement; excluded from historical downloader by strategy decision.", "successor": None, "evidence_url": None},
    "IBVENTURES": {"reason": "No replacement; excluded from historical downloader by strategy decision.", "successor": None, "evidence_url": None},
    "LITL": {"reason": "No replacement; excluded from historical downloader by strategy decision.", "successor": None, "evidence_url": None},
    "PIRAMAN": {"reason": "No replacement; excluded from historical downloader by strategy decision.", "successor": None, "evidence_url": None},
    "REIAGRO": {"reason": "No replacement; excluded from historical downloader by strategy decision.", "successor": None, "evidence_url": None},
    "SDREAMS": {"reason": "No replacement; excluded from historical downloader by strategy decision.", "successor": None, "evidence_url": None},
    "STERLINBIO": {"reason": "No replacement; excluded from historical downloader by strategy decision.", "successor": None, "evidence_url": None},
    "BHUSHANSTL": {"reason": "Successor mapping supplied by user.", "successor": "TATASTEEL", "evidence_url": None},
    "CENTURYTEX": {"reason": "Successor mapping supplied by user.", "successor": "CENTURYTEXT", "evidence_url": None},
    "AKZOINDIA": {
        "reason": "Renamed from Akzo Nobel India Limited to JSW Dulux Limited in April 2026.",
        "successor": "JSWDULUX",
        "evidence_url": "https://nsearchives.nseindia.com/content/circulars/CML73652.pdf",
    },
    "AMARAJA": {
        "reason": "Amara Raja Batteries renamed Amara Raja Energy & Mobility.",
        "successor": "ARE&M",
        "evidence_url": "https://www.amararajaeandm.com/Investors/stock-info",
    },
    "BHARATFIN": {
        "reason": "Amalgamated into IndusInd Bank under a scheme of arrangement.",
        "successor": "INDUSINDBK",
        "evidence_url": "https://niftyindices.com/Press_Release/ind_prs14122018.pdf",
    },
    "IBULHSGFIN": {
        "reason": "Renamed from Indiabulls Housing Finance to Sammaan Capital.",
        "successor": "SAMMAANCAP",
        "evidence_url": "https://www.sharekhan.com/bulletin/change-in-security-name-and-symbol-indiabulls-housing-finance-limited-288384",
    },
    "CAIRN": {
        "reason": "Merged into Vedanta and delisted in April 2017.",
        "successor": "VEDL",
        "evidence_url": "https://www.moneycontrol.com/news/business/companies/cairn-vedanta-merger-effective-april-11-companies-to-retain-brand-identity-2256979.html",
    },
    "CMC": {
        "reason": "Amalgamated with Tata Consultancy Services, appointed date 2015-04-01.",
        "successor": "TCS",
        "evidence_url": "https://www.moneycontrol.com/news/business/earnings/cmc-q3-net-profit22-to-rs-7211-cr-1356277.html",
    },
    "JUBLINGRY": {"reason": "Successor mapping supplied by user.", "successor": "JUBLFOOD", "evidence_url": None},
    "JBCHEPHARM": {"reason": "Merged with Torrent Pharma effective 2026-07-17; share-exchange ratio required for portfolio conversion.", "successor": "TORNTPHARM", "evidence_url": None},
    "JPASSOCIAT": {"reason": "Keep as-is per strategy decision.", "successor": "JPASSOCIAT", "evidence_url": None},
    "OBC": {"reason": "Successor mapping supplied by user.", "successor": "PNB", "evidence_url": None},
    "ORACLE": {"reason": "Successor mapping supplied by user.", "successor": "OFSS", "evidence_url": None},
    "PATNI": {"reason": "Successor mapping supplied by user.", "successor": "TECHM", "evidence_url": None},
    "PIRAMAL": {"reason": "Successor mapping supplied by user.", "successor": "PPLPHARMA", "evidence_url": None},
    "RUCHISOYA": {"reason": "Successor mapping supplied by user.", "successor": "PATANJALI", "evidence_url": None},
    "STERLITE": {"reason": "Successor mapping supplied by user.", "successor": "VEDL", "evidence_url": None},
    "SKSMICRO": {"reason": "Successor mapping supplied by user.", "successor": "BHARATFIN", "evidence_url": None},
    "SINTEX": {"reason": "Special handling required; no replacement applied.", "successor": None, "evidence_url": None},
    "TV18BRDCST": {"reason": "Successor mapping supplied by user.", "successor": "NW18", "evidence_url": None},
    "TVSMNCRPS": {"reason": "Successor mapping supplied by user.", "successor": "TVSHLTD", "evidence_url": None},
    "GRUH": {
        "reason": "Amalgamated into Bandhan Bank following NCLT approval in 2019.",
        "successor": "BANDHANBNK",
        "evidence_url": "https://www.moneycontrol.com/news/business/markets/bandhan-bank-rallies-3-after-nclt-okays-merger-of-gruh-finance-4129941.html",
    },
    "DHFL": {
        "reason": "Corporate insolvency resolution; Piramal's resolution plan was approved.",
        "successor": "Piramal Finance / Piramal Capital & Housing Finance",
        "evidence_url": "https://nsearchives.nseindia.com/corporate/DHFL_09062021105829_1960_clarification__regarding_resolution_plan_status_dt_09062021.pdf",
    },
    "HDFC": {
        "reason": "Amalgamated into HDFC Bank, effective 2023-07-01.",
        "successor": "HDFCBANK",
        "evidence_url": "https://www.hdfcbank.com/content/bbp/repositories/723fb80a-2dde-42a3-9793-7ae1be57c87f/?path=%2FFooter%2FAbout+Us%2FOther+stakeholders%27+Information%2FNew+Issuance%2FKey_Information_Document_18_Dec_2023.pdf",
    },
    "MINDTREE": {
        "reason": "Amalgamated with Larsen & Toubro Infotech.",
        "successor": "LTIMINDTREE",
        "evidence_url": "https://archives.nseindia.com/corporate/MINDTREE_14102022124212_105SubmissionofnewspaperpublicationOctober142022.pdf",
    },
    "MOTHERSUMI": {
        "reason": "Demerger and group restructuring; successor entity renamed Samvardhana Motherson.",
        "successor": "MOTHERSON / MSUMI",
        "evidence_url": "https://nsearchives.nseindia.com/corporate/MOTHERSUMI_26032021230312_NSE.pdf",
    },
    "RANBAXY": {
        "reason": "Merged into Sun Pharma and delisted after the merger.",
        "successor": "SUNPHARMA",
        "evidence_url": "https://www.daiichisankyo.com/media/press_release/detail/index_3515.html",
    },
    "SATYAM": {
        "reason": "Acquired by Tech Mahindra, rebranded Mahindra Satyam, then merged into Tech Mahindra.",
        "successor": "TECHM",
        "evidence_url": "https://www.techmahindra.com/about-us/",
    },
}


def main():
    universe_name = sys.argv[1].lower() if len(sys.argv) == 2 else "nifty500"
    service = UniverseService()
    snapshots = service._history_snapshots(universe_name)
    rows = []

    for symbol in service.history_symbols(
        universe_name, "1900-01-01", "2100-01-01"
    ):
        appearances = snapshots[
            snapshots["symbols"].str.split(",").apply(
                lambda values: symbol in [value.strip() for value in values]
            )
        ]
        first_member_date = appearances["effective_date"].min()
        last_member_date = appearances["effective_date"].max()
        price_file = Path("data/prices") / f"{symbol}.parquet"

        if not price_file.exists():
            action = VERIFIED_ACTIONS.get(symbol, {})
            rows.append({
                "symbol": symbol,
                "issue": "no_yahoo_price_series",
                "reason": action.get("reason", (
                    "Old ticker has no Yahoo price series; corporate action "
                    "(delisting, merger, rename, or vendor-symbol change) "
                    "requires verification"
                )),
                "successor": action.get("successor"),
                "evidence_url": action.get("evidence_url"),
                "first_member_date": first_member_date.date(),
                "last_member_date": last_member_date.date(),
                "first_price_date": None,
                "last_price_date": None,
            })
            continue

        price_dates = pd.to_datetime(
            pd.read_parquet(price_file, columns=["Date"])["Date"]
        )
        if price_dates.max() < last_member_date:
            rows.append({
                "symbol": symbol,
                "issue": "price_series_ends_before_last_membership",
                "reason": "Price series ends before the last recorded index membership date.",
                "successor": None,
                "evidence_url": None,
                "first_member_date": first_member_date.date(),
                "last_member_date": last_member_date.date(),
                "first_price_date": price_dates.min().date(),
                "last_price_date": price_dates.max().date(),
            })

    output = Path(f"reports/output/{universe_name}_historical_data_gaps.csv")
    output.parent.mkdir(parents=True, exist_ok=True)
    report = pd.DataFrame(rows).sort_values(["issue", "symbol"])
    report.to_csv(output, index=False)
    print(f"Wrote {len(report)} rows to {output}")
    print(report.groupby("issue").size().to_string())


if __name__ == "__main__":
    main()
