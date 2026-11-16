"""Truncated MAE research for the SkyQ New London book.

The measurement intentionally stops at the first touch of the base 2R target,
matching the "walk-away" MAE definition: heat after a trade would already have
been closed is not part of the trade's lived experience.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from datetime import date
from math import isfinite

import pandas as pd

from .backtest import BacktestResult, EntryScan, TRADE_COLUMNS, collect_entries
from .config import DEFAULT_END, DEFAULT_START, BookConfig
from .strategy import Entry, Trade, simulate_trade


@dataclass(frozen=True)
class MaeObservation:
    entry: Entry
    month: pd.Period
    mae_points: float
    mae_pct_range: float
    target_hit: bool
    bars: int
    end_time: pd.Timestamp


@dataclass
class MaeStopResult:
    stat: str
    quantile: float
    min_observations: int
    base_trades: pd.DataFrame
    mae_trades: pd.DataFrame
    observations: pd.DataFrame
    monthly_stats: pd.DataFrame
    config: BookConfig
    start: date
    end: date
    sessions: int
    london_sessions: int
    no_break: int
    invalid_stop: int
    entry_count: int
    usable_count: int
    skipped_for_history: int
    session_dates: list[date]
    range_capped: int = 0


def _round_to_tick(price: float, tick_size: float) -> float:
    return round(price / tick_size) * tick_size


def measure_truncated_mae(
    entry: Entry,
    day_1m: pd.DataFrame,
    config: BookConfig,
) -> MaeObservation:
    """Measure adverse excursion only until the base target is touched."""

    direction = 1 if entry.side == "long" else -1
    future = day_1m[day_1m.index > entry.entry_time]
    range_points = entry.london_high - entry.london_low
    mae = 0.0
    bars = 0
    target_hit = False
    end_time = entry.entry_time

    for timestamp, bar in future.iterrows():
        bars += 1
        high = float(bar["high"])
        low = float(bar["low"])
        if entry.side == "long":
            mae = max(mae, entry.entry_price - low)
            reached_target = high >= entry.target_price
        else:
            mae = max(mae, high - entry.entry_price)
            reached_target = low <= entry.target_price

        if reached_target:
            target_hit = True
            end_time = timestamp
            break
        if timestamp.time() >= config.exit_time:
            end_time = timestamp
            break
        end_time = timestamp

    pct = 100.0 * mae / range_points if range_points > 0 else 0.0
    return MaeObservation(
        entry=entry,
        month=pd.Timestamp(entry.day).to_period("M"),
        mae_points=float(mae),
        mae_pct_range=float(pct),
        target_hit=bool(target_hit),
        bars=int(bars),
        end_time=end_time,
    )


def observations_frame(observations: list[MaeObservation]) -> pd.DataFrame:
    rows = []
    for obs in observations:
        rows.append(
            {
                "day": obs.entry.day,
                "month": str(obs.month),
                "side": obs.entry.side,
                "entry_time": obs.entry.entry_time,
                "entry_price": obs.entry.entry_price,
                "london_range_points": obs.entry.london_high - obs.entry.london_low,
                "mae_points": obs.mae_points,
                "mae_pct_range": obs.mae_pct_range,
                "target_hit": obs.target_hit,
                "bars": obs.bars,
                "end_time": obs.end_time,
            }
        )
    return pd.DataFrame(rows)


def monthly_mae_quantiles(
    observations: pd.DataFrame,
    quantile: float,
) -> pd.DataFrame:
    """Per-month count and quantile of truncated MAE as % of London range."""

    if observations.empty:
        return pd.DataFrame(columns=["month", "count", "quantile", "mean", "median", "max"])
    grouped = observations.groupby("month", sort=True)["mae_pct_range"]
    frame = grouped.agg(count="count", mean="mean", median="median", max="max")
    frame["quantile"] = grouped.quantile(quantile)
    return frame.reset_index()


def make_mae_stop_entry(
    entry: Entry,
    mae_pct_range: float,
    config: BookConfig,
) -> Entry | None:
    """Replace the prior-bar stop with a prior-month MAE-derived distance."""

    range_points = entry.london_high - entry.london_low
    if range_points <= 0 or not isfinite(mae_pct_range):
        return None
    buffer = config.stop_buffer_ticks * config.tick_size
    stop_distance = max(
        (mae_pct_range / 100.0) * range_points + buffer,
        config.tick_size,
    )
    if stop_distance <= 0:
        return None

    if entry.side == "long":
        stop_price = entry.entry_price - stop_distance
        target_price = entry.entry_price + config.target_r * stop_distance
    else:
        stop_price = entry.entry_price + stop_distance
        target_price = entry.entry_price - config.target_r * stop_distance

    target_price = _round_to_tick(target_price, config.tick_size)
    risk_dollars = stop_distance * config.point_value * config.contracts
    return replace(
        entry,
        stop_price=float(stop_price),
        target_price=float(target_price),
        risk_points=float(stop_distance),
        risk_dollars=float(risk_dollars),
        prior_extreme=float(stop_price),
    )


def run_prior_month_mae_stop(
    bars_1m: pd.DataFrame,
    config: BookConfig | None = None,
    quantile: float = 0.90,
    min_observations: int = 10,
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
    stat: str = "quantile",
) -> MaeStopResult:
    """Use last month's truncated MAE percentile or mean as the stop distance.

    The prior month is the only source of the stop statistic.  No current-month
    trades contribute to the stop used by that month.  ``stat="mean"`` uses the
    prior month's arithmetic mean instead of a percentile.
    """

    config = config or BookConfig()
    if stat not in {"quantile", "mean"}:
        raise ValueError("stat must be 'quantile' or 'mean'")
    if not 0 < quantile < 1:
        raise ValueError("quantile must be between 0 and 1")
    if min_observations < 1:
        raise ValueError("min_observations must be positive")

    scan: EntryScan = collect_entries(bars_1m, config=config, start=start, end=end)
    observations = [
        measure_truncated_mae(entry, scan.day_frames[entry.day], config)
        for entry in scan.entries
    ]
    obs_frame = observations_frame(observations)
    stats = monthly_mae_quantiles(obs_frame, quantile)
    stats_by_month = stats.set_index("month") if not stats.empty else pd.DataFrame()

    base_rows: list[Trade] = []
    mae_rows: list[dict] = []
    skipped_for_history = 0
    usable_count = 0

    for obs in observations:
        month = str(obs.month)
        previous_month = str(obs.month - 1)
        if previous_month not in stats_by_month.index:
            skipped_for_history += 1
            continue
        row = stats_by_month.loc[previous_month]
        if int(row["count"]) < min_observations:
            skipped_for_history += 1
            continue

        base_trade = simulate_trade(obs.entry, scan.day_frames[obs.entry.day], config)
        base_rows.append(base_trade)

        stop_pct = float(row["mean"] if stat == "mean" else row["quantile"])
        mae_entry = make_mae_stop_entry(obs.entry, stop_pct, config)
        if mae_entry is None:
            skipped_for_history += 1
            continue
        trade = simulate_trade(mae_entry, scan.day_frames[obs.entry.day], config)
        record = asdict(trade)
        record["mae_stop_pct_range"] = stop_pct
        record["prior_month_mae_count"] = int(row["count"])
        record["prior_month_mae_points"] = float(
            (stop_pct / 100.0) * (obs.entry.london_high - obs.entry.london_low)
        )
        record["measured_mae_points"] = obs.mae_points
        record["measured_target_hit"] = obs.target_hit
        mae_rows.append(record)
        usable_count += 1

    base_frame = pd.DataFrame(
        [asdict(trade) for trade in base_rows],
        columns=TRADE_COLUMNS,
    )
    mae_columns = TRADE_COLUMNS + [
        "mae_stop_pct_range",
        "prior_month_mae_count",
        "prior_month_mae_points",
        "measured_mae_points",
        "measured_target_hit",
    ]
    mae_frame = pd.DataFrame(mae_rows, columns=mae_columns)

    return MaeStopResult(
        stat=stat,
        quantile=quantile,
        min_observations=min_observations,
        base_trades=base_frame,
        mae_trades=mae_frame,
        observations=obs_frame,
        monthly_stats=stats,
        config=config,
        start=start,
        end=end,
        sessions=scan.sessions,
        london_sessions=scan.london_sessions,
        no_break=scan.no_break,
        invalid_stop=scan.invalid_stop,
        entry_count=len(scan.entries),
        usable_count=usable_count,
        skipped_for_history=skipped_for_history,
        session_dates=scan.session_dates,
        range_capped=scan.range_capped,
    )


def run_best_backtest(
    bars_1m: pd.DataFrame,
    config: BookConfig | None = None,
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
) -> BacktestResult:
    """Run the researched default book: 0.90% range cap + prior-month MAE q50.

    The range cap is applied before the prior-month MAE statistics are built, so
    wide-range sessions do not influence the stop distance used in the book.
    """

    config = replace(
        config or BookConfig(),
        range_cap_pct=0.90,
        mae_stop_quantile=0.50,
    )
    result = run_prior_month_mae_stop(
        bars_1m,
        config=config,
        quantile=0.50,
        min_observations=10,
        start=start,
        end=end,
    )
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
