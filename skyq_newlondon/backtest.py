"""Day-by-day replay for the SkyQ_NewLondon book."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date

import pandas as pd

from .config import BookConfig, DEFAULT_END, DEFAULT_START
from .data import group_by_day, resample_5m
from .strategy import (
    Entry,
    Trade,
    build_entry,
    first_break,
    london_range,
    simulate_trade,
)


@dataclass
class EntryScan:
    """The one-per-day entry stream before an exit model is applied."""

    entries: list[Entry]
    day_frames: dict[date, pd.DataFrame]
    sessions: int
    london_sessions: int
    no_break: int
    invalid_stop: int
    session_dates: list[date]
    range_capped: int = 0


@dataclass
class BacktestResult:
    trades: pd.DataFrame
    config: BookConfig
    start: date
    end: date
    sessions: int
    london_sessions: int
    no_break: int
    invalid_stop: int
    session_dates: list[date]
    range_capped: int = 0


TRADE_COLUMNS = list(Trade.__dataclass_fields__.keys())


def collect_entries(
    bars_1m: pd.DataFrame,
    config: BookConfig | None = None,
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
) -> EntryScan:
    """Collect the first valid breakout entry for every weekday session."""

    config = config or BookConfig()
    if bars_1m.empty:
        raise ValueError("bars_1m is empty")

    five_1m = resample_5m(bars_1m)
    one_by_day = group_by_day(bars_1m)
    five_by_day = group_by_day(five_1m)

    sessions = 0
    london_sessions = 0
    no_break = 0
    invalid_stop = 0
    range_capped = 0
    session_dates: list[date] = []
    entries: list[Entry] = []
    day_frames: dict[date, pd.DataFrame] = {}

    for day in sorted(one_by_day):
        if day < start or day > end or day.weekday() >= 5:
            continue

        day_1m = one_by_day[day]
        times_1m = day_1m.index.time
        day_1m = day_1m[
            (times_1m >= config.london_start) & (times_1m <= config.exit_time)
        ]
        if day_1m.empty:
            continue
        sessions += 1
        session_dates.append(day)
        day_frames[day] = day_1m

        day_5m = five_by_day.get(day)
        if day_5m is None or day_5m.empty:
            continue
        times_5m = day_5m.index.time
        day_5m = day_5m[
            (times_5m >= config.london_start) & (times_5m < config.exit_time)
        ]
        if day_5m.empty:
            continue

        london = london_range(day_5m, config)
        if london is None:
            continue
        london_sessions += 1

        signal = first_break(day_1m, london, config)
        if signal is None:
            no_break += 1
            continue

        entry = build_entry(day_5m, signal, london, config)
        if entry is None:
            invalid_stop += 1
            continue

        if config.range_cap_pct is not None:
            range_pct = 100.0 * (entry.london_high - entry.london_low) / entry.entry_price
            if range_pct > config.range_cap_pct:
                # The setup is intentionally skipped; it is not a second trade.
                range_capped += 1
                continue

        # One entry is made, so the day is finished whether the trade wins,
        # loses, or times out.  No second side and no re-entry.
        entries.append(entry)

    return EntryScan(
        entries=entries,
        day_frames=day_frames,
        sessions=sessions,
        london_sessions=london_sessions,
        no_break=no_break,
        invalid_stop=invalid_stop,
        session_dates=session_dates,
        range_capped=range_capped,
    )


def run_backtest(
    bars_1m: pd.DataFrame,
    config: BookConfig | None = None,
    start: date = DEFAULT_START,
    end: date = DEFAULT_END,
) -> BacktestResult:
    """Replay every weekday session once, with at most one trade per day."""

    config = config or BookConfig()
    scan = collect_entries(bars_1m, config=config, start=start, end=end)
    trades = [
        simulate_trade(entry, scan.day_frames[entry.day], config)
        for entry in scan.entries
    ]
    frame = pd.DataFrame([asdict(trade) for trade in trades], columns=TRADE_COLUMNS)
    return BacktestResult(
        trades=frame,
        config=config,
        start=start,
        end=end,
        sessions=scan.sessions,
        london_sessions=scan.london_sessions,
        no_break=scan.no_break,
        invalid_stop=scan.invalid_stop,
        session_dates=scan.session_dates,
        range_capped=scan.range_capped,
    )
