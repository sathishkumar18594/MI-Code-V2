"""Deduplicate extracted sector events and surface conflicts for manual validation."""

import argparse
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "data/universe/sector_changes_candidates.csv")
    parser.add_argument("--output", type=Path, default=ROOT / "data/universe/sector_changes_review.csv")
    parser.add_argument("--start-date", default="2020-04-30", help="Earliest valid baseline date")
    args = parser.parse_args()

    events = pd.read_csv(args.input, parse_dates=["effective_date"])
    events = events[events["effective_date"] > pd.Timestamp(args.start_date)].copy()
    identity = ["universe", "effective_date", "action", "symbol"]
    events["source_occurrences"] = events.groupby(identity)["source_url"].transform("size")
    events = events.sort_values(["effective_date", "universe", "symbol", "action", "source_url"])
    events = events.drop_duplicates(identity, keep="first").copy()

    conflicting = events.groupby(["universe", "effective_date", "symbol"])["action"].transform("nunique") > 1
    events["review_status"] = "AUTO_DEDUPLICATED"
    events.loc[conflicting, "review_status"] = "CONFLICT"
    events["effective_date"] = events["effective_date"].dt.date.astype(str)
    events.to_csv(args.output, index=False)
    print(f"Wrote {len(events)} review events ({int(conflicting.sum())} conflicts) to {args.output}")


if __name__ == "__main__":
    main()
