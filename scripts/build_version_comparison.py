"""Build the public version comparison for SkyQ_NewLondon.

This intentionally reruns every variant through the same engine so the table
uses one metrics implementation.  It is a research artifact, not a live signal.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skyq_newlondon.backtest import BacktestResult, run_backtest  # noqa: E402
from skyq_newlondon.config import DEFAULT_END, DEFAULT_START, BookConfig  # noqa: E402
from skyq_newlondon.data import load_1m  # noqa: E402
from skyq_newlondon.mae import (  # noqa: E402
    MaeStopResult,
    run_best_backtest,
    run_prior_month_mae_stop,
)
from skyq_newlondon.report import compute_metrics  # noqa: E402


def as_backtest(result: MaeStopResult) -> BacktestResult:
    return BacktestResult(
        trades=result.mae_trades,
        config=result.config,
        start=result.start,
        end=result.end,
        sessions=result.sessions,
        london_sessions=result.london_sessions,
        no_break=result.no_break,
        invalid_stop=result.invalid_stop,
        session_dates=result.session_dates,
        range_capped=result.range_capped,
    )


def summarize(name: str, role: str, status: str, result: BacktestResult, note: str) -> dict:
    metrics = compute_metrics(result.trades, result)
    trades = result.trades
    exits = trades["exit_reason"].value_counts().to_dict() if not trades.empty else {}
    return {
        "variant": name,
        "role": role,
        "status": status,
        "trades": metrics["trades"],
        "win_rate_pct": metrics["win_rate_pct"],
        "net_pnl": metrics["net_pnl"],
        "profit_factor": metrics["profit_factor"],
        "expectancy_per_trade": metrics["expectancy_per_trade"],
        "avg_r": metrics["avg_r"],
        "max_drawdown": metrics["max_drawdown"],
        "sharpe_daily_annualized": metrics["sharpe_daily_annualized"],
        "sortino_daily_annualized": metrics["sortino_daily_annualized"],
        "avg_win": metrics["avg_win"],
        "avg_loss": metrics["avg_loss"],
        "reward_risk": metrics["reward_risk"],
        "breakeven_win_rate_pct": metrics["breakeven_win_rate_pct"],
        "avg_stop_points": metrics["avg_stop_points"],
        "avg_risk_dollars": metrics["avg_risk_dollars"],
        "targets": int(exits.get("target", 0)),
        "stops": int(exits.get("stop", 0)),
        "time_exits": int(exits.get("time", 0)),
        "range_capped_days": metrics["range_capped_days"],
        "positive_months": metrics["positive_months"],
        "negative_months": metrics["negative_months"],
        "positive_years": metrics["positive_years"],
        "negative_years": metrics["negative_years"],
        "net_per_year": metrics["net_per_year"],
        "note": note,
    }


def markdown(rows: list[dict]) -> str:
    headers = [
        "Variant",
        "Role",
        "Decision",
        "Trades",
        "Win %",
        "Net P&L",
        "PF",
        "Max DD",
        "Sharpe",
        "Sortino",
        "Avg stop",
        "Target / stop / time",
    ]
    lines = [
        "# SkyQ_NewLondon — version comparison",
        "",
        "All rows use NQ 1-minute data, 2018-10-23 through 2026-10-23, one contract,",
        "$0.62/side commission, one tick of entry/stop/time slippage, and stop-first",
        "same-bar treatment. Returns are backtest dollars, not live results.",
        "",
        "| " + " | ".join(headers) + " |",
        "|" + "|".join(["---"] * len(headers)) + "|",
    ]
    for row in rows:
        values = dict(row)
        values["profit_factor"] = (
            "n/a" if row["profit_factor"] is None else f"{row['profit_factor']:.3f}"
        )
        values["sharpe"] = (
            "n/a"
            if row["sharpe_daily_annualized"] is None
            else f"{row['sharpe_daily_annualized']:.2f}"
        )
        values["sortino"] = (
            "n/a"
            if row["sortino_daily_annualized"] is None
            else f"{row['sortino_daily_annualized']:.2f}"
        )
        lines.append(
            "| {variant} | {role} | {status} | {trades:,} | {win_rate_pct:.2f}% | "
            "${net_pnl:,.2f} | {profit_factor} | ${max_drawdown:,.2f} | "
            "{sharpe} | {sortino} | {avg_stop_points:.2f} pts | "
            "{targets} / {stops} / {time_exits} |".format(**values)
        )
    lines += [
        "",
        "## Decision notes",
        "",
    ]
    for row in rows:
        lines.append(f"- **{row['variant']}** ({row['role']}): {row['note']}")
    lines += [
        "",
        "## Honest interpretation",
        "",
        "- The default is the best **in-sample research** version, not a validated",
        "  live system. It has a positive eight-year net, but 2026 is negative and",
        "  the result is still dependent on 2021, 2023, and 2025.",
        "- The base book is retained exactly as a reproducibility reference. It",
        "  loses money after costs and must not be marketed as profitable.",
        "- Wide stops can produce a larger nominal P&L while making most trades",
        "  time exits. That is a different risk profile, not a free improvement.",
        "- Before any live use: add a capped stop, walk-forward windows, contract",
        "  roll handling, and a drawdown-aware position-size limit.",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    bars = load_1m(PROJECT_ROOT / "data" / "nq_1m.parquet")
    base_config = BookConfig()
    rows: list[dict] = []

    base = run_backtest(bars, config=base_config)
    rows.append(
        summarize(
            "Base book",
            "Reference",
            "Rejected as default",
            base,
            "Original rules. Loses after costs; retained behind `--base` for reproducibility.",
        )
    )

    capped = run_backtest(bars, config=replace(base_config, range_cap_pct=0.90))
    rows.append(
        summarize(
            "Range cap only",
            "Research candidate",
            "Superseded",
            capped,
            "The 0.90% London-range cap alone improves the base, but the MAE q50 stop adds more.",
        )
    )

    for quantile in (0.50, 0.75, 0.90, 0.95):
        mae = run_prior_month_mae_stop(
            bars,
            config=base_config,
            quantile=quantile,
            min_observations=10,
            start=DEFAULT_START,
            end=DEFAULT_END,
        )
        result = as_backtest(mae)
        decision = "Candidate, not default" if quantile == 0.50 else "Rejected as default"
        note = (
            "Improves the base, but is dominated by the capped q50 version."
            if quantile == 0.50
            else "Wider stop increases drawdown and turns many trades into time exits."
        )
        rows.append(
            summarize(
                f"MAE q{int(quantile * 100)} (uncapped)",
                "Stop study",
                decision,
                result,
                note,
            )
        )

    mean = run_prior_month_mae_stop(
        bars,
        config=base_config,
        quantile=0.50,
        min_observations=10,
        start=DEFAULT_START,
        end=DEFAULT_END,
        stat="mean",
    )
    rows.append(
        summarize(
            "MAE prior-month mean (uncapped)",
            "Stop study",
            "Rejected as default",
            as_backtest(mean),
            "The literal mean stop is wider, has a larger drawdown, and is heavily 2025-dependent.",
        )
    )

    best = run_best_backtest(bars, config=base_config)
    rows.append(
        summarize(
            "MAE q50 + 0.90% range cap",
            "DEFAULT",
            "Selected",
            best,
            "Lowest drawdown among the improved variants, fewer time exits than q75+, and the best net/risk balance in-sample.",
        )
    )

    frame = pd.DataFrame(rows)
    csv_path = PROJECT_ROOT / "logs" / "nq_london_version_comparison.csv"
    md_path = PROJECT_ROOT / "logs" / "nq_london_version_comparison.md"
    frame.to_csv(csv_path, index=False)
    md_path.write_text(markdown(rows), encoding="utf-8")

    display = frame[
        [
            "variant",
            "trades",
            "win_rate_pct",
            "net_pnl",
            "profit_factor",
            "max_drawdown",
            "sharpe_daily_annualized",
            "sortino_daily_annualized",
            "avg_stop_points",
        ]
    ]
    print(display.to_string(index=False))
    print(f"\nWrote {csv_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
