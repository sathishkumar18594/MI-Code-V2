from pathlib import Path
import io
import re
import time

import pandas as pd
import requests

from utils.logger import logger


class UniverseService:

    # Historical tickers deliberately not downloaded: they have no usable
    # successor series for this strategy.
    HISTORICAL_DOWNLOAD_EXCLUSIONS = {
        "ARE&M", "ARE& M", "COX&KINGS", "GSKCONS", "GUJNRECOKE", "IBVENTURES",
        "LITL", "PIRAMAN", "REIAGRO", "SDREAMS", "STERLINBIO",
    }

    URLS = {
        "nifty500": "https://niftyindices.com/IndexConstituent/ind_nifty500list.csv",
        "nifty50": "https://niftyindices.com/IndexConstituent/ind_nifty50list.csv",
        "nifty100": "https://niftyindices.com/IndexConstituent/ind_nifty100list.csv",
        "nifty200": "https://niftyindices.com/IndexConstituent/ind_nifty200list.csv",
        "midcap250": "https://niftyindices.com/IndexConstituent/ind_niftymidcap250list.csv",
        "midcap150": "https://niftyindices.com/IndexConstituent/ind_niftymidcap150list.csv",
        "niftymidcap150": "https://niftyindices.com/IndexConstituent/ind_niftymidcap150list.csv",
        # Sector universes used by the standalone sector portfolio.  Keep the
        # keys lowercase: they are also the names used for saved snapshots.
        "niftyauto": "https://niftyindices.com/IndexConstituent/ind_niftyautolist.csv",
        "niftybank": "https://niftyindices.com/IndexConstituent/ind_niftybanklist.csv",
        "niftycapitalgoods": "https://niftyindices.com/IndexConstituent/ind_niftycapitalgoodslist.csv",
        "niftycement": "https://niftyindices.com/IndexConstituent/ind_niftycementlist.csv",
        "niftychemicals": "https://niftyindices.com/IndexConstituent/ind_niftychemicalslist.csv",
        "niftycommercialtransportservices": "https://niftyindices.com/IndexConstituent/ind_niftycommercialandtransportserviceslist.csv",
        "niftyconstruction": "https://niftyindices.com/IndexConstituent/ind_niftyconstructionlist.csv",
        "niftyconsumerdurables": "https://niftyindices.com/IndexConstituent/ind_niftyconsumerdurableslist.csv",
        "niftyconsumerservices": "https://niftyindices.com/IndexConstituent/ind_niftyconsumerserviceslist.csv",
        "niftyfinancialservices": "https://niftyindices.com/IndexConstituent/ind_niftyfinancialserviceslist.csv",
        "niftyfinancialservices2550": "https://niftyindices.com/IndexConstituent/ind_niftyfinancialservices2550list.csv",
        "niftyfinancialservicesexbank": "https://niftyindices.com/IndexConstituent/ind_niftyfinancialservicesexbanklist.csv",
        "niftyfmcg": "https://niftyindices.com/IndexConstituent/ind_niftyfmcglist.csv",
        "niftyhealthcare": "https://niftyindices.com/IndexConstituent/ind_niftyhealthcarelist.csv",
        "niftyhospitals": "https://niftyindices.com/IndexConstituent/ind_niftyhospitalslist.csv",
        "niftyhousingfinance": "https://niftyindices.com/IndexConstituent/ind_niftyhousingfinancelist.csv",
        "niftyinsurance": "https://niftyindices.com/IndexConstituent/ind_niftyinsurancelist.csv",
        "niftyit": "https://niftyindices.com/IndexConstituent/ind_niftyitlist.csv",
        "niftymedia": "https://niftyindices.com/IndexConstituent/ind_niftymedialist.csv",
        "niftymetal": "https://niftyindices.com/IndexConstituent/ind_niftymetallist.csv",
        "niftynbfc": "https://niftyindices.com/IndexConstituent/ind_niftynbfclist.csv",
        "niftyoilgas": "https://niftyindices.com/IndexConstituent/ind_niftyoilgaslist.csv",
        "niftypharma": "https://niftyindices.com/IndexConstituent/ind_niftypharmalist.csv",
        "niftypower": "https://niftyindices.com/IndexConstituent/ind_niftypowerlist.csv",
        "niftyprivatebank": "https://niftyindices.com/IndexConstituent/ind_niftyprivatebanklist.csv",
        "niftypsubank": "https://niftyindices.com/IndexConstituent/ind_niftypsubanklist.csv",
        "niftyrealty": "https://niftyindices.com/IndexConstituent/ind_niftyrealtylist.csv",
        "niftyreitsrealty": "https://niftyindices.com/IndexConstituent/ind_niftyreitsrealtylist.csv",
        "niftyretail": "https://niftyindices.com/IndexConstituent/ind_niftyretaillist.csv",
        "niftytelecommunications": "https://niftyindices.com/IndexConstituent/ind_niftytelecommunicationslist.csv",
        "nifty500healthcare": "https://niftyindices.com/IndexConstituent/ind_nifty500healthcarelist.csv",
        "niftymidsmallfinancialservices": "https://niftyindices.com/IndexConstituent/ind_niftymidsmallfinancialserviceslist.csv",
        "niftymidsmallhealthcare": "https://niftyindices.com/IndexConstituent/ind_niftymidsmallhealthcarelist.csv",
        "niftymidsmallittelecom": "https://niftyindices.com/IndexConstituent/ind_niftymidsmallittelecomlist.csv",
    }

    # The constituent CSV file names are inconsistent across sector indices.
    # Resolve them from the official index page instead of guessing a filename.
    SECTOR_PAGES = {
        "niftyauto": "nifty-auto", "niftybank": "nifty-bank", "niftycapitalgoods": "nifty-capital-goods", "niftycement": "nifty-cement", "niftychemicals": "nifty-chemicals", "niftycommercialtransportservices": "nifty-commercial---transport-services", "niftyconstruction": "nifty-construction", "niftyconsumerdurables": "nifty-consumer-durables-index", "niftyconsumerservices": "nifty-consumer-services", "niftyfinancialservices": "nifty-financial-services", "niftyfinancialservices2550": "nifty-financial-services-25-50-index", "niftyfinancialservicesexbank": "nifty-financial--services-ex-bank", "niftyfmcg": "nifty-fmcg", "niftyhealthcare": "nifty-healthcare-index", "niftyhospitals": "nifty-hospitals", "niftyhousingfinance": "nifty-housing-finance", "niftyinsurance": "nifty-insurance", "niftyit": "nifty-it", "niftymedia": "nifty-media", "niftymetal": "nifty-metal", "niftynbfc": "nifty-nbfc", "niftyoilgas": "nifty-oil-and-gas-index", "niftypharma": "nifty-pharma", "niftypower": "nifty-power", "niftyprivatebank": "nifty-private-bank", "niftypsubank": "nifty-psu-bank", "niftyrealty": "nifty-realty", "niftyreitsrealty": "nifty-reits---realty", "niftyretail": "nifty-retail", "niftytelecommunications": "nifty-telecommunications", "nifty500healthcare": "nifty500-healthcare", "niftymidsmallfinancialservices": "nifty-midsmall--financial-services", "niftymidsmallhealthcare": "nifty-midsmallhealthcare", "niftymidsmallittelecom": "nifty-midsmall--it-telecom",
    }

    def __init__(self):

        self.folder = Path("data_v2/universe")
        self.folder.mkdir(parents=True, exist_ok=True)
        self.history_folder = self.folder / "history"
        self.history_folder.mkdir(parents=True, exist_ok=True)

    def _download(self, url):

        headers = {
            "User-Agent": (
                "Mozilla/5.0 "
                "(Macintosh; Intel Mac OS X 10_15_7)"
            )
        }

        retries = 3

        for attempt in range(1, retries + 1):

            try:

                logger.info(f"Downloading {url}")

                response = requests.get(
                    url,
                    headers=headers,
                    timeout=(10, 60)
                )

                response.raise_for_status()

                return pd.read_csv(
                    io.StringIO(response.text)
                )

            except Exception as ex:

                logger.warning(
                    f"Attempt {attempt}/{retries} failed: {ex}"
                )

                if attempt == retries:
                    raise

                time.sleep(5)

    def _sector_constituent_url(self, page_slug: str) -> str:
        """Read the official page and return its linked constituent CSV."""
        page_url = (
            "https://www.niftyindices.com/indices/equity/sectoral-indices/"
            f"{page_slug}"
        )
        headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
        response = requests.get(page_url, headers=headers, timeout=(10, 60))
        response.raise_for_status()
        match = re.search(
            r"https?://[^\"'\s]+/IndexConstituent/[^\"'\s]+\.csv",
            response.text,
            flags=re.IGNORECASE,
        )
        if not match:
            raise ValueError(f"No constituent CSV link found on {page_url}")
        return match.group(0).replace("&amp;", "&")

    def refresh(self, universe_name: str):

        # Configuration names use readable underscores (for example
        # ``nifty_financial_services``); NSE's constituent endpoint omits
        # them.  Preserve the original name for local files and history.
        url_key = universe_name.lower().replace("_", "")
        if universe_name not in self.URLS and url_key not in self.URLS:
            raise ValueError(f"Unsupported universe: {universe_name}")

        logger.info(f"Refreshing {universe_name}")

        source_url = (
            self._sector_constituent_url(self.SECTOR_PAGES[url_key])
            if url_key in self.SECTOR_PAGES
            else self.URLS.get(universe_name, self.URLS[url_key])
        )
        df = self._download(source_url)

        file = self.folder / f"{universe_name}.csv"
        previous_symbols = set()
        if file.exists():
            previous_symbols = set(pd.read_csv(file)["Symbol"].dropna())

        df.to_csv(
            file,
            index=False
        )

        snapshot_date = pd.Timestamp.now(tz="Asia/Kolkata").date().isoformat()
        snapshot_folder = self.history_folder / universe_name
        snapshot_folder.mkdir(parents=True, exist_ok=True)
        snapshot_file = snapshot_folder / f"{snapshot_date}.csv"
        df.to_csv(snapshot_file, index=False)

        current_symbols = set(df["Symbol"].dropna())
        if previous_symbols:
            changes = pd.DataFrame(
                [
                    {
                        "effective_date": snapshot_date,
                        "action": "ADD",
                        "symbol": symbol,
                    }
                    for symbol in sorted(current_symbols - previous_symbols)
                ]
                + [
                    {
                        "effective_date": snapshot_date,
                        "action": "REMOVE",
                        "symbol": symbol,
                    }
                    for symbol in sorted(previous_symbols - current_symbols)
                ]
            )
            if not changes.empty:
                changes_file = self.folder / f"{universe_name}_changes.csv"
                changes.to_csv(
                    changes_file,
                    mode="a",
                    header=not changes_file.exists(),
                    index=False,
                )
                logger.info(
                    f"{universe_name}: {len(current_symbols - previous_symbols)} "
                    f"added, {len(previous_symbols - current_symbols)} removed."
                )

        logger.info(
            f"{universe_name}.csv and {snapshot_file} saved with {len(df)} stocks."
        )

        return df

    def get_universe(self, universe_name: str):

        file = self.folder / f"{universe_name}.csv"

        if file.exists():

            logger.info(
                f"Loading {universe_name}.csv"
            )

            df = pd.read_csv(file)

            return df["Symbol"].tolist()

        logger.info(
            f"{universe_name}.csv not found. Downloading..."
        )

        df = self.refresh(universe_name)

        return df["Symbol"].tolist()

    def import_history(self, universe_name: str, source_file: str):
        """Import full constituent snapshots from a downloaded index ledger."""
        history = pd.read_csv(source_file)
        required = {"effective_date", "index_type", "symbols"}
        missing = required - set(history.columns)
        if missing:
            raise ValueError(
                f"Universe history is missing required columns: {sorted(missing)}"
            )

        history = history[
            history["index_type"].str.lower() == universe_name.lower()
        ].copy()
        history["effective_date"] = pd.to_datetime(history["effective_date"])
        history["symbols"] = history["symbols"].fillna("")
        history = history.sort_values("effective_date").drop_duplicates(
            subset=["effective_date"], keep="last"
        )
        if history.empty:
            raise ValueError(f"No {universe_name} snapshots found in {source_file}")

        output = self.history_folder / f"{universe_name}_history.csv"
        history[["effective_date", "symbols"]].to_csv(output, index=False)
        logger.info(
            f"Imported {len(history)} {universe_name} historical snapshots to {output}."
        )

    def get_universe_as_of(self, universe_name: str, date) -> list[str]:
        """Return the Nifty universe that was active on the requested date."""
        snapshots = self._history_snapshots(universe_name)
        date = pd.Timestamp(date).normalize()
        snapshots = snapshots[snapshots["effective_date"] <= date]
        if snapshots.empty:
            raise ValueError(
                f"No {universe_name} history snapshot exists on or before {date.date()}"
            )
        symbols = snapshots.iloc[-1]["symbols"]
        return [symbol.strip() for symbol in symbols.split(",") if symbol.strip()]

    def history_symbols(self, universe_name: str, start_date, end_date) -> list[str]:
        """Return the union of symbols needed for a historical date range."""
        snapshots = self._history_snapshots(universe_name)
        start = pd.Timestamp(start_date).normalize()
        end = pd.Timestamp(end_date).normalize()
        baseline = snapshots[snapshots["effective_date"] <= start].tail(1)
        changes = snapshots[
            (snapshots["effective_date"] > start)
            & (snapshots["effective_date"] <= end)
        ]
        selected = pd.concat([baseline, changes]).drop_duplicates(
            subset=["effective_date"]
        )
        symbols = set()
        for value in selected["symbols"]:
            symbols.update(symbol.strip() for symbol in value.split(",") if symbol.strip())
        return sorted(symbols)

    def history_file(self, universe_name: str) -> Path:
        """Resolve the authoritative imported ledger for a universe.

        An explicitly named official ledger takes precedence over the legacy
        generic ledger. Snapshot files captured by refresh() are layered on
        top separately by ``_history_snapshots``.
        """
        normalized = universe_name.lower()
        files = {file.name.lower(): file for file in self.history_folder.glob("*.csv")}
        official = files.get(f"{normalized}_official_history.csv")
        if official is not None:
            return official
        return files.get(
            f"{normalized}_history.csv",
            self.history_folder / f"{normalized}_history.csv",
        )

    def build_sector_history_from_parent(
        self,
        sector_universe: str,
        parent_universe: str = "nifty500",
    ) -> pd.DataFrame:
        """Create point-in-time sector eligibility from a parent index ledger.

        The sector's downloaded constituent list supplies its classification;
        the historical parent ledger supplies the eligibility date.  This keeps
        a stock out until it was actually present in the supplied Nifty 500
        history, rather than backfilling today's Nifty 500 membership.
        """
        sector_file = self.folder / f"{sector_universe}.csv"
        if not sector_file.exists():
            raise FileNotFoundError(f"Missing current sector list: {sector_file}")
        sector_symbols = set(
            pd.read_csv(sector_file)["Symbol"].dropna().astype(str).str.strip()
        )
        parent = self._history_snapshots(parent_universe)
        if parent.empty:
            raise ValueError(f"No parent history found for {parent_universe}")

        rows = []
        for row in parent.itertuples(index=False):
            eligible = {
                symbol.strip() for symbol in str(row.symbols).split(",")
                if symbol.strip()
            }
            rows.append({
                "effective_date": pd.Timestamp(row.effective_date).date().isoformat(),
                "symbols": ",".join(sorted(sector_symbols & eligible)),
            })
        history = pd.DataFrame(rows).drop_duplicates(
            subset=["effective_date"], keep="last"
        )
        # Callers normalize universe names to lowercase before lookup.
        output = self.history_folder / f"{sector_universe.lower()}_history.csv"
        history.to_csv(output, index=False)
        return history

    def _history_snapshots(self, universe_name: str) -> pd.DataFrame:
        snapshots = []
        normalized = universe_name.lower()
        imported = self.history_file(normalized)
        if imported.exists():
            snapshots.append(pd.read_csv(imported, parse_dates=["effective_date"]))

        # Snapshots captured by refresh() extend the imported ledger going
        # forward without overwriting its historical effective dates.
        snapshot_folders = [
            folder for folder in self.history_folder.iterdir()
            if folder.is_dir() and folder.name.lower() == normalized
        ]
        for snapshot_folder in snapshot_folders:
            for file in snapshot_folder.glob("*.csv"):
                date = pd.to_datetime(file.stem, errors="coerce")
                if pd.isna(date):
                    continue
                symbols = pd.read_csv(file)["Symbol"].dropna().astype(str)
                snapshots.append(
                    pd.DataFrame(
                        [{
                            "effective_date": date,
                            "symbols": ",".join(symbols),
                        }]
                    )
                )

        if not snapshots:
            return pd.DataFrame(columns=["effective_date", "symbols"])
        return pd.concat(snapshots, ignore_index=True).sort_values(
            "effective_date"
        ).drop_duplicates(subset=["effective_date"], keep="last")
