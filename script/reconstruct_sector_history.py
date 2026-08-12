"""Reconstruct point-in-time sector universes by replaying change logs backwards.

The input ledger must contain every membership-changing event for every sector.
Required columns: universe,effective_date,action,symbol.  ``action`` may be
ADD/REMOVE or INCLUSION/EXCLUSION.  The script starts with the latest saved
universe and creates a snapshot for each requested historical date.
"""

import argparse
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.universe_service import UniverseService


ADD_ACTIONS = {"ADD", "ADDITION", "INCLUSION", "INCLUDE"}
REMOVE_ACTIONS = {"REMOVE", "REMOVAL", "EXCLUSION", "EXCLUDE"}


def normalize_changes(path: Path) -> pd.DataFrame:
    changes = pd.read_csv(path)
    required = {"universe", "effective_date", "action", "symbol"}
    missing = required - set(changes.columns)
    if missing:
        raise ValueError(f"Change log missing columns: {sorted(missing)}")
    changes = changes.copy()
    changes["universe"] = changes["universe"].astype(str).str.upper().str.strip()
    changes["symbol"] = changes["symbol"].astype(str).str.upper().str.strip()
    changes["effective_date"] = pd.to_datetime(changes["effective_date"])
    changes["action"] = changes["action"].astype(str).str.upper().str.strip()
    unknown = set(changes["action"]) - ADD_ACTIONS - REMOVE_ACTIONS
    if unknown:
        raise ValueError(f"Unsupported actions: {sorted(unknown)}")
    return changes.dropna(subset=["effective_date"])


def compact_name(value: str) -> str:
    """Make official display names comparable with local file names."""
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def resolve_universe_names(names: list[str], service: UniverseService) -> dict[str, str]:
    """Map ledger labels such as ``Nifty Oil and Gas`` to local file names.

    The source ledger can retain the official human-readable index name; output
    files use the existing repository convention (for example NIFTY_OIL_GAS).
    """
    local_names = [path.stem for path in service.folder.glob("NIFTY_*.csv")]
    by_compact = {compact_name(name): name for name in local_names}
    resolved = {}
    for name in names:
        key = compact_name(name)
        candidate = by_compact.get(key) or by_compact.get(key.replace("AND", ""))
        if candidate is None:
            raise ValueError(f"No current universe file matches change-log universe: {name}")
        resolved[name] = candidate
    return resolved


def reconstruct(current_symbols: set[str], changes: pd.DataFrame, as_of: pd.Timestamp):
    """Return the membership at ``as_of`` plus counts for the audit trail."""
    membership = set(current_symbols)
    reverse = changes[changes["effective_date"] > as_of].sort_values(
        "effective_date", ascending=False
    )
    reversed_additions = reversed_removals = 0
    for event in reverse.itertuples(index=False):
        if event.action in ADD_ACTIONS:
            membership.discard(event.symbol)
            reversed_additions += 1
        else:
            membership.add(event.symbol)
            reversed_removals += 1
    return sorted(membership), reversed_additions, reversed_removals


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--changes", type=Path, required=True)
    parser.add_argument("--dates", required=True, nargs="+", help="YYYY-MM-DD dates")
    parser.add_argument("--universes", nargs="*", help="Defaults to all ledger universes")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--launch-dates",
        type=Path,
        default=ROOT / "data/universe/sector_launch_dates.csv",
        help="Optional CSV with universe,available_from; snapshots before availability are skipped.",
    )
    parser.add_argument(
        "--validate-existing",
        action="store_true",
        help="Compare reconstructed output to an existing snapshot; it is not replaced unless --overwrite is also set.",
    )
    args = parser.parse_args()

    changes = normalize_changes(args.changes)
    available = set(changes["universe"])
    requested = [name.upper() for name in args.universes] if args.universes else sorted(available)
    missing = set(requested) - available
    if missing:
        raise ValueError(f"No change log entries for: {sorted(missing)}")
    dates = sorted(pd.Timestamp(value).normalize() for value in args.dates)

    service = UniverseService()
    universe_names = resolve_universe_names(requested, service)
    launch_dates = {}
    if args.launch_dates.exists():
        launches = pd.read_csv(args.launch_dates, parse_dates=["available_from"])
        launch_dates = dict(zip(launches["universe"], launches["available_from"].dt.normalize()))
    audit = []
    for ledger_universe in requested:
        universe = universe_names[ledger_universe]
        current_file = service.folder / f"{universe}.csv"
        if not current_file.exists():
            raise FileNotFoundError(f"Missing current universe: {current_file}")
        current = pd.read_csv(current_file)
        if "Symbol" not in current:
            raise ValueError(f"{current_file} has no Symbol column")
        symbols = set(current["Symbol"].dropna().astype(str).str.upper().str.strip())
        sector_changes = changes[changes["universe"] == ledger_universe]
        output_dir = service.history_folder / universe
        output_dir.mkdir(parents=True, exist_ok=True)

        for as_of in dates:
            output = output_dir / f"{as_of.date().isoformat()}.csv"
            launch_date = launch_dates.get(universe)
            if launch_date is not None and as_of < launch_date:
                audit.append({
                    "universe": universe,
                    "ledger_universe": ledger_universe,
                    "as_of_date": as_of.date(),
                    "status": "PRE_LAUNCH",
                    "available_from": launch_date.date(),
                })
                continue
            members, undo_adds, undo_removes = reconstruct(symbols, sector_changes, as_of)
            result = {
                "universe": universe,
                "ledger_universe": ledger_universe,
                "as_of_date": as_of.date(),
                "constituents": len(members),
                "reversed_inclusions": undo_adds,
                "reversed_exclusions": undo_removes,
            }
            if not members:
                result["status"] = "NO_MEMBERSHIP"
                audit.append(result)
                continue
            if output.exists() and args.validate_existing:
                known = set(pd.read_csv(output)["Symbol"].dropna().astype(str).str.upper().str.strip())
                calculated = set(members)
                result["known_constituents"] = len(known)
                result["missing_from_reconstruction"] = ",".join(sorted(known - calculated))
                result["unexpected_in_reconstruction"] = ",".join(sorted(calculated - known))
                result["matches_existing"] = known == calculated
            if output.exists() and not args.overwrite:
                result["status"] = "VALIDATED_EXISTING" if args.validate_existing else "SKIPPED_EXISTS"
                audit.append(result)
                continue
            pd.DataFrame({"Symbol": members}).to_csv(output, index=False)
            result["status"] = "WRITTEN"
            audit.append(result)

    audit_file = service.history_folder / "sector_reconstruction_audit.csv"
    pd.DataFrame(audit).to_csv(audit_file, index=False)
    print(f"Wrote audit: {audit_file}")


if __name__ == "__main__":
    main()
