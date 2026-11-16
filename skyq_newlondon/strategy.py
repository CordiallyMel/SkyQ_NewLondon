"""The SkyQ New London breakout rules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from .config import BookConfig


@dataclass(frozen=True)
class LondonRange:
    high: float
    low: float
    bars: int


@dataclass(frozen=True)
class BreakSignal:
    side: str
    trigger_time: pd.Timestamp
    raw_entry: float


@dataclass(frozen=True)
class Entry:
    day: date
    side: str
    entry_time: pd.Timestamp
    raw_entry: float
    entry_price: float
    stop_price: float
    target_price: float
    risk_points: float
    risk_dollars: float
    london_high: float
    london_low: float
    prior_bar_time: pd.Timestamp
    prior_extreme: float
    entry_slippage_points: float


@dataclass(frozen=True)
class Trade:
    day: date
    side: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    stop_price: float
    target_price: float
    risk_points: float
    risk_dollars: float
    london_high: float
    london_low: float
    prior_bar_time: pd.Timestamp
    prior_extreme: float
    exit_reason: str
    gross_points: float
    gross_pnl: float
    commission: float
    slippage_points: float
    slippage_dollars: float
    net_pnl: float
    r_multiple: float
    mfe_points: float
    mae_points: float
    bars_held: int


def _round_to_tick(price: float, tick_size: float) -> float:
    return round(price / tick_size) * tick_size


def london_range(day_5m: pd.DataFrame, config: BookConfig) -> LondonRange | None:
    """High/low of 04:00-09:00 ET 5-minute bars (09:00 is excluded)."""

    if day_5m.empty:
        return None
    times = day_5m.index.time
    window = day_5m[
        (times >= config.london_start) & (times < config.london_end)
    ]
    if len(window) < config.min_london_bars:
        return None
    high = float(window["high"].max())
    low = float(window["low"].min())
    if high <= low:
        return None
    return LondonRange(high=high, low=low, bars=len(window))


def prior_extreme(
    day_5m: pd.DataFrame,
    entry_time: pd.Timestamp,
    side: str,
    config: BookConfig,
) -> tuple[float, pd.Timestamp] | None:
    """Stop anchor: low (long) or high (short) of the last completed 5m bar(s).

    A 09:30 entry therefore uses the 09:25 bar, not the 09:30 bar that is still
    forming.  This is the no-lookahead definition of "most recent" low/high.
    """

    cutoff = entry_time.floor("5min")
    prior = day_5m[day_5m.index < cutoff].tail(config.stop_lookback_bars)
    if prior.empty:
        return None
    if side == "long":
        extreme = float(prior["low"].min())
    else:
        extreme = float(prior["high"].max())
    return extreme, prior.index[-1]


def first_break(
    day_1m: pd.DataFrame,
    london: LondonRange,
    config: BookConfig,
) -> BreakSignal | None:
    """First 1-minute break of either London level inside the entry window.

    The London levels are treated as stop orders active at 09:30.  A gap
    through a level fills at the 1-minute open; otherwise the fill is at the
    level.  If one huge minute trades through both levels, the side closer to
    that minute's open is treated as first.
    """

    times = day_1m.index.time
    window = day_1m[
        (times >= config.entry_start) & (times < config.entry_end)
    ]
    for timestamp, bar in window.iterrows():
        long_hit = float(bar["high"]) >= london.high
        short_hit = float(bar["low"]) <= london.low
        if not long_hit and not short_hit:
            continue

        if long_hit and short_hit:
            open_price = float(bar["open"])
            if open_price >= london.high:
                side = "long"
            elif open_price <= london.low:
                side = "short"
            else:
                long_distance = london.high - open_price
                short_distance = open_price - london.low
                side = "long" if long_distance <= short_distance else "short"
        elif long_hit:
            side = "long"
        else:
            side = "short"

        open_price = float(bar["open"])
        if side == "long":
            raw_entry = open_price if open_price > london.high else london.high
        else:
            raw_entry = open_price if open_price < london.low else london.low
        return BreakSignal(side=side, trigger_time=timestamp, raw_entry=raw_entry)
    return None


def build_entry(
    day_5m: pd.DataFrame,
    signal: BreakSignal,
    london: LondonRange,
    config: BookConfig,
) -> Entry | None:
    """Attach the prior 5-minute stop and the fixed 2R target."""

    anchor = prior_extreme(day_5m, signal.trigger_time, signal.side, config)
    if anchor is None:
        return None
    prior_price, prior_time = anchor
    slip = config.slippage_ticks * config.tick_size
    buffer = config.stop_buffer_ticks * config.tick_size

    if signal.side == "long":
        entry_price = signal.raw_entry + slip
        stop_price = prior_price - buffer
        risk = entry_price - stop_price
        if risk <= 0:
            return None
        target = _round_to_tick(entry_price + config.target_r * risk, config.tick_size)
    else:
        entry_price = signal.raw_entry - slip
        stop_price = prior_price + buffer
        risk = stop_price - entry_price
        if risk <= 0:
            return None
        target = _round_to_tick(entry_price - config.target_r * risk, config.tick_size)

    return Entry(
        day=signal.trigger_time.date(),
        side=signal.side,
        entry_time=signal.trigger_time,
        raw_entry=signal.raw_entry,
        entry_price=float(entry_price),
        stop_price=float(stop_price),
        target_price=float(target),
        risk_points=float(risk),
        risk_dollars=float(risk * config.point_value * config.contracts),
        london_high=london.high,
        london_low=london.low,
        prior_bar_time=prior_time,
        prior_extreme=float(prior_price),
        entry_slippage_points=float(slip),
    )


def simulate_trade(
    entry: Entry,
    day_1m: pd.DataFrame,
    config: BookConfig,
) -> Trade:
    """Walk subsequent 1-minute bars and resolve stop, target, or 16:00 exit.

    Exits start on the minute *after* the entry trigger because the intrabar
    order of the entry minute is unknown.  If a later bar contains both the
    stop and target, the stop is assumed first (conservative fill).
    """

    slip = config.slippage_ticks * config.tick_size
    direction = 1 if entry.side == "long" else -1
    future = day_1m[day_1m.index > entry.entry_time]

    exit_time = entry.entry_time
    exit_price = entry.entry_price
    exit_reason = "time"
    exit_slippage = 0.0
    mfe = 0.0
    mae = 0.0
    bars_held = 0
    exited = False

    for timestamp, bar in future.iterrows():
        bars_held += 1
        high = float(bar["high"])
        low = float(bar["low"])
        open_price = float(bar["open"])

        if entry.side == "long":
            mfe = max(mfe, high - entry.entry_price)
            mae = min(mae, low - entry.entry_price)
        else:
            mfe = max(mfe, entry.entry_price - low)
            mae = min(mae, entry.entry_price - high)

        if timestamp.time() >= config.exit_time:
            exit_time = timestamp
            exit_price = open_price - direction * slip
            exit_reason = "time"
            exit_slippage = slip
            exited = True
            break

        if entry.side == "long":
            if low <= entry.stop_price:
                exit_time = timestamp
                exit_price = min(open_price, entry.stop_price) - slip
                exit_reason = "stop"
                exit_slippage = slip
                exited = True
                break
            if high >= entry.target_price:
                exit_time = timestamp
                exit_price = entry.target_price
                exit_reason = "target"
                exit_slippage = 0.0
                exited = True
                break
        else:
            if high >= entry.stop_price:
                exit_time = timestamp
                exit_price = max(open_price, entry.stop_price) + slip
                exit_reason = "stop"
                exit_slippage = slip
                exited = True
                break
            if low <= entry.target_price:
                exit_time = timestamp
                exit_price = entry.target_price
                exit_reason = "target"
                exit_slippage = 0.0
                exited = True
                break

    if not exited:
        if future.empty:
            exit_time = entry.entry_time
            exit_price = entry.entry_price
        else:
            last = future.iloc[-1]
            exit_time = future.index[-1]
            exit_price = float(last["close"]) - direction * slip
        exit_reason = "time"
        exit_slippage = slip

    gross_points = (exit_price - entry.entry_price) * direction
    gross_pnl = gross_points * config.point_value * config.contracts
    commission = config.commission
    net_pnl = gross_pnl - commission
    slippage_points = entry.entry_slippage_points + exit_slippage
    slippage_dollars = slippage_points * config.point_value * config.contracts
    risk_dollars = entry.risk_dollars

    return Trade(
        day=entry.day,
        side=entry.side,
        entry_time=entry.entry_time,
        exit_time=exit_time,
        entry_price=entry.entry_price,
        exit_price=float(exit_price),
        stop_price=entry.stop_price,
        target_price=entry.target_price,
        risk_points=entry.risk_points,
        risk_dollars=risk_dollars,
        london_high=entry.london_high,
        london_low=entry.london_low,
        prior_bar_time=entry.prior_bar_time,
        prior_extreme=entry.prior_extreme,
        exit_reason=exit_reason,
        gross_points=float(gross_points),
        gross_pnl=float(gross_pnl),
        commission=float(commission),
        slippage_points=float(slippage_points),
        slippage_dollars=float(slippage_dollars),
        net_pnl=float(net_pnl),
        r_multiple=float(net_pnl / risk_dollars) if risk_dollars else 0.0,
        mfe_points=float(mfe),
        mae_points=float(mae),
        bars_held=int(bars_held),
    )
