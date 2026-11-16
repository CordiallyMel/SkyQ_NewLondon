"""Prior-month truncated-MAE stop experiment for SkyQ_NewLondon.

Each current-month entry uses the prior calendar month's selected quantile or
mean of MAE as a percentage of the London range.  MAE is measured only until the
base 2R target is touched, then truncated.  Stops are placed that distance from
the entry and the target remains 2R from the new stop.

Examples:
    python scripts/run_mae_stop.py
    python scripts/run_mae_stop.py --quantiles 0.5 0.75 0.9 0.95
    python scripts/run_mae_stop.py --include-mean
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import asdict
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skyq_newlondon.backtest import BacktestResult  # noqa: E402
from skyq_newlondon.config import DEFAULT_END, DEFAULT_START, BookConfig  # noqa: E402
from skyq_newlondon.data import load_1m  # noqa: E402
from skyq_newlondon.mae import run_prior_month_mae_stop  # noqa: E402
from skyq_newlondon.report import compute_metrics  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=PROJECT_ROOT / "data" / "nq_1m.parquet",
    )
    parser.add_argument("--start", default=DEFAULT_START.isoformat())
    parser.add_argument("--end", default=DEFAULT_END.isoformat())
    parser.add_argument("--quantiles", nargs="+", type=float, default=[0.50, 0.75, 0.90, 0.95])
    parser.add_argument(
        "--include-mean",
        action="store_true",
        help="also run the prior-month arithmetic-mean MAE stop",
    )
    parser.add_argument("--min-observations", type=int, default=10)
    parser.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "logs")
    parser.add_argument("--label", default="nq_london_8y_mae_stop")
    return parser.parse_args()


def _result(
    trades: pd.DataFrame,
    config: BookConfig,
    start,
    end,
    sessions: int,
    london_sessions: int,
    no_break: int,
    invalid_stop: int,
    session_dates,
) -> BacktestResult:
    return BacktestResult(
        trades=trades,
        config=config,
        start=start,
        end=end,
        sessions=sessions,
        london_sessions=london_sessions,
        no_break=no_break,
        invalid_stop=invalid_stop,
        session_dates=session_dates,
    )


def _summary_row(
    label: str,
    quantile: float,
    metrics: dict,
    stat: str = "quantile",
) -> dict:
    return {
        "variant": label,
        "quantile": quantile,
        "stat": stat,
        "trades": metrics["trades"],
        "win_rate_pct": metrics["win_rate_pct"],
        "net_pnl": metrics["net_pnl"],
        "profit_factor": metrics["profit_factor"],
        "expectancy": metrics["expectancy_per_trade"],
        "avg_r": metrics["avg_r"],
        "max_drawdown": metrics["max_drawdown"],
        "avg_stop_points": metrics["avg_stop_points"],
        "targets": int(metrics.get("target_exits", 0)),
        "stops": int(metrics.get("stop_exits", 0)),
        "time_exits": int(metrics.get("time_exits", 0)),
    }


def main() -> int:
    args = parse_args()
    start = pd.Timestamp(args.start).date()
    end = pd.Timestamp(args.end).date()
    config = BookConfig()
    bars = load_1m(args.data, start=start, end=end)
    output = Path(args.out_dir)
    output.mkdir(parents=True, exist_ok=True)

    summaries: list[dict] = []
    all_observations = None
    all_monthly = None

    variants = [
        (f"q{int(round(quantile * 100)):02d}", quantile, "quantile")
        for quantile in args.quantiles
    ]
    if args.include_mean:
        variants.append(("mean", 0.50, "mean"))

    for name, quantile, stat in variants:
        result = run_prior_month_mae_stop(
            bars,
            config=config,
            quantile=quantile,
            min_observations=args.min_observations,
            start=start,
            end=end,
            stat=stat,
        )
        base_result = _result(
            result.base_trades,
            config,
            start,
            end,
            result.sessions,
            result.london_sessions,
            result.no_break,
            result.invalid_stop,
            result.session_dates,
        )
        mae_result = _result(
            result.mae_trades,
            config,
            start,
            end,
            result.sessions,
            result.london_sessions,
            result.no_break,
            result.invalid_stop,
            result.session_dates,
        )
        base_metrics = compute_metrics(result.base_trades, base_result)
        mae_metrics = compute_metrics(result.mae_trades, mae_result)

        # Add exit counts without changing the shared report surface.
        for metrics, trades in [(base_metrics, result.base_trades), (mae_metrics, result.mae_trades)]:
            if not trades.empty:
                exits = trades["exit_reason"].value_counts()
                metrics["target_exits"] = int(exits.get("target", 0))
                metrics["stop_exits"] = int(exits.get("stop", 0))
                metrics["time_exits"] = int(exits.get("time", 0))

        summaries.append(_summary_row("base_subset", quantile, base_metrics, stat))
        summaries.append(_summary_row("mae_stop", quantile, mae_metrics, stat))

        tag = f"{args.label}_{name}"
        result.base_trades.to_csv(output / f"{tag}_base_trades.csv", index=False)
        result.mae_trades.to_csv(output / f"{tag}_trades.csv", index=False)
        if all_observations is None:
            all_observations = result.observations
        if all_monthly is None:
            all_monthly = result.monthly_stats.copy()
            all_monthly["quantile"] = quantile
            all_monthly["stat"] = stat
        else:
            monthly = result.monthly_stats.copy()
            monthly["quantile"] = quantile
            monthly["stat"] = stat
            all_monthly = pd.concat([all_monthly, monthly], ignore_index=True)

        print(
            f"{name}: base subset {len(result.base_trades):4d} trades "
            f"${base_metrics['net_pnl']:>10,.2f} | "
            f"MAE {len(result.mae_trades):4d} trades ${mae_metrics['net_pnl']:>10,.2f} "
            f"PF {mae_metrics['profit_factor']} | "
            f"usable {result.usable_count}/{result.entry_count}"
        )

    summary = pd.DataFrame(summaries)
    summary.to_csv(output / f"{args.label}_summary.csv", index=False)
    if all_observations is not None:
        all_observations.to_csv(output / f"{args.label}_observations.csv", index=False)
    if all_monthly is not None:
        all_monthly.to_csv(output / f"{args.label}_monthly_stats.csv", index=False)

    report = [
        "SkyQ_NewLondon — Prior-Month Truncated-MAE Stop Experiment",
        "=" * 66,
        "MAE definition: adverse excursion from entry until the base 2R target is",
        "touched, then truncated.  If no target, measured through the 16:00 ET exit.",
        "Stop: prior calendar month's MAE statistic (quantile or mean), expressed",
        "as % of the London range; target remains 2R from the new stop.  No current-month data enters",
        "the stop for that month.",
        "",
        summary.to_string(index=False),
        "",
        "The base_subset rows are the same entry dates as the MAE rows, so the",
        "comparison is apples-to-apples.  Early months without a full prior month",
        "of observations are skipped.",
    ]
    (output / f"{args.label}_report.txt").write_text("\n".join(report), encoding="utf-8")
    print("\n" + "\n".join(report))
    print("\nSaved:")
    for path in sorted(output.glob(f"{args.label}*")):
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
