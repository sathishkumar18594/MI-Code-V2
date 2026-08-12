import csv
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config/strategy.yaml"
OUTPUT = ROOT / "reports/output"
TARGETS = {
    "nifty50": ("NIFTY50", "^NSEI", 3),
    "nifty100": ("NIFTY100", "^CNX100", 3),
    "nifty200": ("NIFTY200", "^CNX200", 5),
    "nifty500": ("NIFTY500", "^CRSLDX", 5),
}
BACKTEST_FILES = {
    "annual.csv", "annual_asset_contribution.csv", "asset_class_performance.csv",
    "circuit_screen.csv", "decisions.csv", "holdings.csv",
    "lower_circuit_filtered_stocks.csv", "metrics.csv", "monthly.csv",
    "monthly_return_matrix.csv", "stock_summary.csv", "summary.csv", "trades.csv",
    "transaction_costs.csv",
}


def main():
    if "--repair" in sys.argv:
        repair_existing_reports()
        return
    if "--nifty100-top10-no-gold" in sys.argv:
        run_variant(
            folder="nifty100_top10_no_gold",
            universe="NIFTY100",
            index_symbol="^CNX100",
            portfolio_size=10,
            hedge_enabled=False,
        )
        return
    if "--nifty100-top10-gold" in sys.argv:
        run_variant(
            folder="nifty100_top10_gold",
            universe="NIFTY100",
            index_symbol="^CNX100",
            portfolio_size=10,
            hedge_enabled=True,
        )
        return
    if "--nifty100-top5-no-gold" in sys.argv:
        run_variant(
            folder="nifty100_top5_no_gold",
            universe="NIFTY100",
            index_symbol="^CNX100",
            portfolio_size=5,
            hedge_enabled=False,
        )
        return
    if "--nifty100-top5-gold" in sys.argv:
        run_variant(
            folder="nifty100_top5_gold",
            universe="NIFTY100",
            index_symbol="^CNX100",
            portfolio_size=5,
            hedge_enabled=True,
        )
        return
    if "--nifty100-top3-no-gold" in sys.argv:
        run_variant(
            folder="nifty100_top3_no_gold",
            universe="NIFTY100",
            index_symbol="^CNX100",
            portfolio_size=3,
            hedge_enabled=False,
        )
        return
    if "--nifty100-top3-gold" in sys.argv:
        run_variant(
            folder="nifty100_top3_gold",
            universe="NIFTY100",
            index_symbol="^CNX100",
            portfolio_size=3,
            hedge_enabled=True,
        )
        return
    if "--nifty50-top3-no-gold" in sys.argv:
        run_variant(
            folder="nifty50_top3_no_gold",
            universe="NIFTY50",
            index_symbol="^NSEI",
            portfolio_size=3,
            hedge_enabled=False,
        )
        return
    if "--nifty50-top3-gold" in sys.argv:
        run_variant(
            folder="nifty50_top3_gold",
            universe="NIFTY50",
            index_symbol="^NSEI",
            portfolio_size=3,
            hedge_enabled=True,
        )
        return
    if "--nifty200-top10-no-gold" in sys.argv:
        run_variant(
            folder="nifty200_top10_no_gold",
            universe="NIFTY200",
            index_symbol="^CNX200",
            portfolio_size=10,
            hedge_enabled=False,
        )
        return
    if "--nifty200-top10-gold" in sys.argv:
        run_variant(
            folder="nifty200_top10_gold",
            universe="NIFTY200",
            index_symbol="^CNX200",
            portfolio_size=10,
            hedge_enabled=True,
        )
        return
    if "--nifty200-top5-no-gold" in sys.argv:
        run_variant(
            folder="nifty200_top5_no_gold",
            universe="NIFTY200",
            index_symbol="^CNX200",
            portfolio_size=5,
            hedge_enabled=False,
        )
        return
    if "--nifty200-top5-gold" in sys.argv:
        run_variant(
            folder="nifty200_top5_gold",
            universe="NIFTY200",
            index_symbol="^CNX200",
            portfolio_size=5,
            hedge_enabled=True,
        )
        return
    if "--nifty500-top10-no-gold" in sys.argv:
        run_variant(
            folder="nifty500_top10_no_gold",
            universe="NIFTY500",
            index_symbol="^CRSLDX",
            portfolio_size=10,
            hedge_enabled=False,
        )
        return
    if "--nifty500-top10-gold" in sys.argv:
        run_variant(
            folder="nifty500_top10_gold",
            universe="NIFTY500",
            index_symbol="^CRSLDX",
            portfolio_size=10,
            hedge_enabled=True,
        )
        return
    if "--parallel" in sys.argv:
        run_parallel()
        return
    original = CONFIG.read_text()
    try:
        for folder, (name, symbol, portfolio_size) in TARGETS.items():
            config = yaml.safe_load(original)
            config["strategy"]["portfolio_size"] = portfolio_size
            config["universe"]["name"] = name
            config["universe"]["market_filter"]["index"]["name"] = name
            config["universe"]["market_filter"]["index"]["symbol"] = symbol
            CONFIG.write_text(yaml.safe_dump(config, sort_keys=False))

            print(f"Running {name} backtest...")
            subprocess.run([str(ROOT / ".venv/bin/python"), "run_backtest.py"], cwd=ROOT, check=True)

            destination = ROOT / "reports" / folder
            destination.mkdir(parents=True, exist_ok=True)
            for old_file in destination.glob("*.csv"):
                if old_file.name not in BACKTEST_FILES:
                    old_file.unlink()
            for report_file in OUTPUT.glob("*.csv"):
                if report_file.name not in BACKTEST_FILES:
                    continue
                shutil.copy2(report_file, destination / report_file.name)
            print(f"Saved {name} reports to {destination}")
    finally:
        CONFIG.write_text(original)


def run_variant(
    folder,
    universe,
    index_symbol,
    portfolio_size,
    hedge_enabled,
):
    """Run one isolated variant without changing the shared strategy file."""
    config = yaml.safe_load(CONFIG.read_text())
    config["strategy"]["portfolio_size"] = portfolio_size
    config["market_hedge"]["enabled"] = hedge_enabled
    config["universe"]["name"] = universe
    config["universe"]["market_filter"]["index"]["name"] = universe
    config["universe"]["market_filter"]["index"]["symbol"] = index_symbol
    config["report"] = {
        "output_directory": str(ROOT / "reports" / folder),
    }

    with tempfile.TemporaryDirectory(prefix="strategy_variant_") as temp_dir:
        config_file = Path(temp_dir) / f"{folder}.yaml"
        config_file.write_text(yaml.safe_dump(config, sort_keys=False))
        environment = os.environ.copy()
        environment["STRATEGY_CONFIG"] = str(config_file)
        subprocess.run(
            [str(ROOT / ".venv/bin/python"), "run_backtest.py"],
            cwd=ROOT,
            env=environment,
            check=True,
        )


def run_parallel():
    """Run each universe in an isolated process, config, and output folder."""
    original = yaml.safe_load(CONFIG.read_text())
    processes = []
    with tempfile.TemporaryDirectory(prefix="universe_backtests_") as temp_dir:
        temp_root = Path(temp_dir)
        for folder, (name, symbol, portfolio_size) in TARGETS.items():
            config = yaml.safe_load(yaml.safe_dump(original))
            config["strategy"]["portfolio_size"] = portfolio_size
            config["universe"]["name"] = name
            config["universe"]["market_filter"]["index"]["name"] = name
            config["universe"]["market_filter"]["index"]["symbol"] = symbol
            config["report"] = {"output_directory": str(ROOT / "reports" / folder)}
            config_file = temp_root / f"{folder}.yaml"
            config_file.write_text(yaml.safe_dump(config, sort_keys=False))
            environment = os.environ.copy()
            environment["STRATEGY_CONFIG"] = str(config_file)
            processes.append((name, subprocess.Popen(
                [str(ROOT / ".venv/bin/python"), "run_backtest.py"],
                cwd=ROOT,
                env=environment,
            )))

        failed = [name for name, process in processes if process.wait() != 0]
    if failed:
        raise SystemExit(f"Backtests failed: {', '.join(failed)}")


def repair_existing_reports():
    for folder, (name, _, _) in TARGETS.items():
        destination = ROOT / "reports" / folder
        for old_file in destination.glob("*.csv"):
            if old_file.name not in BACKTEST_FILES:
                old_file.unlink()

        summary = destination / "summary.csv"
        if summary.exists():
            rows = list(csv.DictReader(summary.open()))
            if rows:
                rows[0]["benchmark_name"] = name
                rows[0]["universe"] = name
                with summary.open("w", newline="") as output:
                    writer = csv.DictWriter(output, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)


if __name__ == "__main__":
    main()
