"""Performance metrics and output files for SkyQ_NewLondon."""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from .backtest import BacktestResult


def _num(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        result = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(result) or math.isinf(result):
        return default
    return result


def _profit_factor(net: pd.Series) -> float | None:
    gains = float(net[net > 0].sum())
    losses = float(-net[net < 0].sum())
    if losses == 0:
        return None
    return gains / losses


def _max_drawdown(equity: pd.Series) -> float:
    if equity.empty:
        return 0.0
    running = equity.cummax()
    drawdown = equity - running
    return float(-drawdown.min())


def _max_consecutive_losses(net: pd.Series) -> int:
    worst = 0
    current = 0
    for value in net:
        if value < 0:
            current += 1
            worst = max(worst, current)
        else:
            current = 0
    return worst


def compute_metrics(trades: pd.DataFrame, result: BacktestResult) -> dict[str, Any]:
    config = result.config
    net = trades["net_pnl"].astype(float) if not trades.empty else pd.Series(dtype=float)
    wins = net[net > 0]
    losses = net[net < 0]
    breakeven = net[net == 0]
    total = len(net)
    years = max((result.end - result.start).days / 365.25, 1e-9)

    daily_index = pd.to_datetime(pd.Series(result.session_dates, dtype="object"))
    daily = pd.Series(0.0, index=daily_index)
    if not trades.empty:
        by_day = trades.groupby("day")["net_pnl"].sum()
        for day, value in by_day.items():
            daily.loc[pd.Timestamp(day)] += float(value)
    daily_std = float(daily.std(ddof=1)) if len(daily) > 1 else 0.0
    sharpe = (
        float(daily.mean() / daily_std * math.sqrt(252))
        if daily_std > 0
        else None
    )
    downside = daily[daily < 0]
    downside_std = (
        float(math.sqrt((downside**2).mean())) if len(downside) else 0.0
    )
    sortino = (
        float(daily.mean() / downside_std * math.sqrt(252))
        if downside_std > 0
        else None
    )

    monthly_pnl = (
        trades.assign(_month=pd.to_datetime(trades["day"]).dt.to_period("M"))
        .groupby("_month")["net_pnl"].sum()
        if not trades.empty
        else pd.Series(dtype=float)
    )
    yearly_pnl = (
        trades.assign(_year=pd.to_datetime(trades["day"]).dt.year)
        .groupby("_year")["net_pnl"].sum()
        if not trades.empty
        else pd.Series(dtype=float)
    )
    positive_months = int((monthly_pnl > 0).sum()) if len(monthly_pnl) else 0
    negative_months = int((monthly_pnl < 0).sum()) if len(monthly_pnl) else 0
    positive_years = int((yearly_pnl > 0).sum()) if len(yearly_pnl) else 0
    negative_years = int((yearly_pnl < 0).sum()) if len(yearly_pnl) else 0

    equity = net.cumsum()
    max_dd = _max_drawdown(equity)
    net_total = float(net.sum())
    gross_profit = float(wins.sum())
    gross_loss = float(-losses.sum())
    profit_factor = _profit_factor(net)

    if trades.empty:
        avg_stop = avg_risk = max_stop = 0.0
        avg_r = 0.0
        long_count = short_count = 0
        commission_total = slippage_total = 0.0
        mfe_1r_pct = mfe_2r_pct = 0.0
    else:
        avg_stop = float(trades["risk_points"].mean())
        max_stop = float(trades["risk_points"].max())
        avg_risk = float(trades["risk_dollars"].mean())
        avg_r = float(trades["r_multiple"].mean())
        long_count = int((trades["side"] == "long").sum())
        short_count = int((trades["side"] == "short").sum())
        commission_total = float(trades["commission"].sum())
        slippage_total = float(trades["slippage_dollars"].sum())
        mfe_1r_pct = 100.0 * float(
            (trades["mfe_points"] >= trades["risk_points"]).mean()
        )
        mfe_2r_pct = 100.0 * float(
            (trades["mfe_points"] >= 2.0 * trades["risk_points"]).mean()
        )

    total_costs = commission_total + slippage_total
    gross_before_commission = net_total + commission_total
    gross_zero_cost = net_total + total_costs
    avg_win = float(wins.mean()) if len(wins) else 0.0
    avg_loss = float(losses.mean()) if len(losses) else 0.0
    reward_risk = (
        avg_win / abs(avg_loss)
        if avg_win > 0 and avg_loss < 0
        else None
    )
    breakeven_win_rate = (
        100.0 / (1.0 + reward_risk) if reward_risk is not None else None
    )

    return {
        "start": result.start.isoformat(),
        "end": result.end.isoformat(),
        "years": round(years, 3),
        "symbol": config.symbol,
        "contracts": config.contracts,
        "point_value": config.point_value,
        "tick_size": config.tick_size,
        "sessions": result.sessions,
        "london_sessions": result.london_sessions,
        "no_break_days": result.no_break,
        "invalid_stop_days": result.invalid_stop,
        "range_capped_days": result.range_capped,
        "trades": total,
        "long_trades": long_count,
        "short_trades": short_count,
        "trades_per_year": round(total / years, 1),
        "win_rate_pct": round(100.0 * len(wins) / total, 2) if total else 0.0,
        "net_pnl": round(net_total, 2),
        "net_points": round(net_total / (config.point_value * config.contracts), 2),
        "gross_profit": round(gross_profit, 2),
        "gross_loss": round(gross_loss, 2),
        "profit_factor": round(profit_factor, 3) if profit_factor is not None else None,
        "expectancy_per_trade": round(net_total / total, 2) if total else 0.0,
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "reward_risk": round(reward_risk, 3) if reward_risk is not None else None,
        "breakeven_win_rate_pct": (
            round(breakeven_win_rate, 2) if breakeven_win_rate is not None else None
        ),
        "breakeven_trades": int(len(breakeven)),
        "positive_months": positive_months,
        "negative_months": negative_months,
        "positive_years": positive_years,
        "negative_years": negative_years,
        "net_per_month": round(net_total / max(len(monthly_pnl), 1), 2),
        "avg_r": round(avg_r, 3),
        "avg_stop_points": round(avg_stop, 2),
        "max_stop_points": round(max_stop, 2),
        "avg_risk_dollars": round(avg_risk, 2),
        "max_drawdown": round(max_dd, 2),
        "max_consecutive_losses": _max_consecutive_losses(net),
        "sharpe_daily_annualized": round(sharpe, 2) if sharpe is not None else None,
        "sortino_daily_annualized": round(sortino, 2) if sortino is not None else None,
        "commission_total": round(commission_total, 2),
        "slippage_total": round(slippage_total, 2),
        "total_costs": round(total_costs, 2),
        "gross_before_commission": round(gross_before_commission, 2),
        "gross_zero_cost": round(gross_zero_cost, 2),
        "mfe_1r_pct": round(mfe_1r_pct, 2),
        "mfe_2r_pct": round(mfe_2r_pct, 2),
        "net_per_year": round(net_total / years, 2),
        "first_trade": str(trades["entry_time"].min()) if total else None,
        "last_trade": str(trades["entry_time"].max()) if total else None,
    }


def _group_table(trades: pd.DataFrame, by: str, label: str) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=[label, "trades", "win_rate_pct", "net_pnl", "profit_factor", "avg_r"])
    rows = []
    for key, group in trades.groupby(by, sort=True):
        net = group["net_pnl"].astype(float)
        pf = _profit_factor(net)
        rows.append(
            {
                label: key,
                "trades": int(len(group)),
                "win_rate_pct": round(100.0 * (net > 0).mean(), 2),
                "net_pnl": round(float(net.sum()), 2),
                "profit_factor": round(pf, 3) if pf is not None else None,
                "avg_r": round(float(group["r_multiple"].mean()), 3),
            }
        )
    return pd.DataFrame(rows)


def yearly_table(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["year", "trades", "win_rate_pct", "net_pnl", "profit_factor", "avg_r", "max_drawdown"])
    frame = trades.copy()
    frame["year"] = pd.to_datetime(frame["day"]).dt.year
    rows = []
    for year, group in frame.groupby("year", sort=True):
        net = group["net_pnl"].astype(float)
        pf = _profit_factor(net)
        rows.append(
            {
                "year": int(year),
                "trades": int(len(group)),
                "win_rate_pct": round(100.0 * (net > 0).mean(), 2),
                "net_pnl": round(float(net.sum()), 2),
                "profit_factor": round(pf, 3) if pf is not None else None,
                "avg_r": round(float(group["r_multiple"].mean()), 3),
                "max_drawdown": round(_max_drawdown(net.cumsum()), 2),
            }
        )
    return pd.DataFrame(rows)


def monthly_table(trades: pd.DataFrame) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame(columns=["month", "trades", "net_pnl"])
    frame = trades.copy()
    frame["month"] = pd.to_datetime(frame["day"]).dt.to_period("M").astype(str)
    rows = []
    for month, group in frame.groupby("month", sort=True):
        net = group["net_pnl"].astype(float)
        rows.append(
            {
                "month": month,
                "trades": int(len(group)),
                "net_pnl": round(float(net.sum()), 2),
                "win_rate_pct": round(100.0 * (net > 0).mean(), 2),
            }
        )
    return pd.DataFrame(rows)


def _md_table(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_No rows._"
    return frame.to_string(index=False)


def format_report(result: BacktestResult, metrics: dict[str, Any]) -> str:
    trades = result.trades
    config = result.config
    yearly = yearly_table(trades)
    side = _group_table(trades, "side", "side")
    exit_reason = _group_table(trades, "exit_reason", "exit_reason")
    monthly = monthly_table(trades)
    positive_months = metrics["positive_months"]
    negative_months = metrics["negative_months"]

    pf = metrics["profit_factor"]
    pf_text = "n/a" if pf is None else f"{pf:.3f}"
    sharpe = metrics["sharpe_daily_annualized"]
    sharpe_text = "n/a" if sharpe is None else f"{sharpe:.2f}"
    sortino = metrics["sortino_daily_annualized"]
    sortino_text = "n/a" if sortino is None else f"{sortino:.2f}"
    rr = metrics["reward_risk"]
    rr_text = "n/a" if rr is None else f"{rr:.3f}"
    be = metrics["breakeven_win_rate_pct"]
    be_text = "n/a" if be is None else f"{be:.2f}%"
    best_mode = config.mae_stop_quantile is not None
    title = (
        "SkyQ_NewLondon — DEFAULT: MAE q50 + 0.90% range cap"
        if best_mode
        else "SkyQ_NewLondon — base research book"
    )
    stop_rule = (
        f"Stop: prior-month MAE q{config.mae_stop_quantile:.2f} of London range "
        f"+ {config.stop_buffer_ticks:g} tick buffer"
        if best_mode
        else f"Stop: {config.stop_buffer_ticks:g} tick(s) beyond the prior "
        f"{config.stop_lookback_bars} completed 5m bar(s)"
    )

    return "\n".join(
        [
            title,
            "=" * 58,
            f"Window: {metrics['start']} to {metrics['end']} ({metrics['years']:.2f} years)",
            f"Instrument: {config.symbol}, {config.contracts} contract(s), ${config.point_value:.2f}/point",
            "Rules: London range 04:00-09:00 ET | first break 09:30-11:00 ET | 2R | one trade/day",
            f"Filter: skip London ranges wider than {config.range_cap_pct:.2f}% of entry price"
            if config.range_cap_pct is not None
            else "Filter: none (base book)",
            f"Costs: ${config.commission_per_side:.2f}/side commission, {config.slippage_ticks:g} tick(s) slippage on entry/stop/time",
            stop_rule,
            "",
            "Headline",
            "-" * 58,
            f"Sessions scanned:       {metrics['sessions']:,}",
            f"London ranges built:    {metrics['london_sessions']:,}",
            f"No-break days:          {metrics['no_break_days']:,}",
            f"Invalid-stop days:      {metrics['invalid_stop_days']:,}",
            f"Range-capped days:      {metrics['range_capped_days']:,}",
            f"Trades:                 {metrics['trades']:,}  ({metrics['long_trades']} long / {metrics['short_trades']} short)",
            f"Win rate:               {metrics['win_rate_pct']:.2f}%",
            f"Net P&L:                ${metrics['net_pnl']:,.2f}  ({metrics['net_points']:,.2f} NQ points)",
            f"  before commission:    ${metrics['gross_before_commission']:,.2f}",
            f"  zero-cost outcome:    ${metrics['gross_zero_cost']:,.2f}",
            f"  commission+slippage:  ${metrics['total_costs']:,.2f}",
            f"Profit factor:          {pf_text}",
            f"Expectancy/trade:       ${metrics['expectancy_per_trade']:,.2f}",
            f"Average R:              {metrics['avg_r']:.3f}R",
            f"Avg win / avg loss:      ${metrics['avg_win']:,.2f} / ${metrics['avg_loss']:,.2f}",
            f"Reward/risk:            {rr_text}",
            f"Break-even win rate:    {be_text} (actual {metrics['win_rate_pct']:.2f}%)",
            f"Max drawdown:           ${metrics['max_drawdown']:,.2f}",
            f"Max consecutive losses: {metrics['max_consecutive_losses']}",
            f"Annualized daily Sharpe:{sharpe_text:>7}",
            f"Annualized daily Sortino:{sortino_text:>7}",
            f"Avg stop:               {metrics['avg_stop_points']:.2f} NQ points (${metrics['avg_risk_dollars']:,.2f} risk)",
            f"Reached 1R / 2R:         {metrics['mfe_1r_pct']:.1f}% / {metrics['mfe_2r_pct']:.1f}%",
            "",
            "Year by year",
            "-" * 58,
            _md_table(yearly),
            "",
            "By side",
            "-" * 58,
            _md_table(side),
            "",
            "By exit",
            "-" * 58,
            _md_table(exit_reason),
            "",
            "Monthly consistency",
            "-" * 58,
            f"Profitable months: {positive_months} | Losing months: {negative_months}",
            f"Profitable years:  {metrics['positive_years']} | Losing years: {metrics['negative_years']}",
            "",
            "Definition notes",
            "-" * 58,
            "• London high/low uses 04:00-08:59 ET 5-minute bars; 09:00 is excluded.",
            "• Entries are stop orders at the London levels, active 09:30-10:59 ET.",
            "• Base stop: one tick beyond the low/high of the last completed 5-minute bar before entry.",
            "• Default stop: prior-month 50th-percentile truncated MAE, expressed as % of London range, plus one tick.",
            "• Default filter: skip a session if the London range exceeds 0.90% of the entry price.",
            "• Entry/exit path is resolved on 1-minute bars; if stop and target share a bar, stop wins.",
            "• 16:00 ET is a time exit; no overnight risk.",
            "• One trade per day; the first side to break is the only trade, win or lose.",
            "• NQ data is a continuous 1-minute series; roll gaps are not separately modeled.",
        ]
    )


def write_outputs(
    result: BacktestResult,
    metrics: dict[str, Any],
    out_dir: str | Path = "logs",
    label: str = "nq_london_8y",
) -> dict[str, Path]:
    output = Path(out_dir)
    output.mkdir(parents=True, exist_ok=True)
    trades = result.trades
    yearly = yearly_table(trades)
    side = _group_table(trades, "side", "side")
    exits = _group_table(trades, "exit_reason", "exit_reason")
    monthly = monthly_table(trades)

    paths = {
        "trades": output / f"{label}_trades.csv",
        "summary": output / f"{label}_summary.json",
        "report": output / f"{label}_report.txt",
        "yearly": output / f"{label}_yearly.csv",
        "side": output / f"{label}_side.csv",
        "exits": output / f"{label}_exits.csv",
        "monthly": output / f"{label}_monthly.csv",
        "equity": output / f"{label}_equity.csv",
    }

    trades.to_csv(paths["trades"], index=False)
    yearly.to_csv(paths["yearly"], index=False)
    side.to_csv(paths["side"], index=False)
    exits.to_csv(paths["exits"], index=False)
    monthly.to_csv(paths["monthly"], index=False)

    if trades.empty:
        equity = pd.DataFrame(columns=["day", "net_pnl", "equity"])
    else:
        by_day = trades.groupby("day", sort=True)["net_pnl"].sum().reset_index()
        by_day["equity"] = by_day["net_pnl"].cumsum()
        equity = by_day
    equity.to_csv(paths["equity"], index=False)

    payload = {
        **metrics,
        "config": asdict(result.config),
        "yearly": yearly.to_dict(orient="records"),
        "side": side.to_dict(orient="records"),
        "exits": exits.to_dict(orient="records"),
        "monthly": monthly.to_dict(orient="records"),
    }

    def _default(value: Any) -> str:
        if isinstance(value, (date, datetime, pd.Timestamp)):
            return str(value)
        return str(value)

    paths["summary"].write_text(
        json.dumps(payload, indent=2, default=_default),
        encoding="utf-8",
    )
    paths["report"].write_text(format_report(result, metrics), encoding="utf-8")
    return paths
