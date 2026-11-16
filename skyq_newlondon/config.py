"""Configuration for the SkyQ_NewLondon NQ book."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, time

NY_TZ = "America/New_York"

# The parquet file covers 2017-04 through 2026-10.  This is the exact
# eight-calendar-year window used for the headline test.
DEFAULT_START = date(2018, 10, 23)
DEFAULT_END = date(2026, 10, 23)


@dataclass(frozen=True)
class BookConfig:
    """Strategy and execution assumptions.

    The London range is measured on 5-minute bars.  Entry and exit fills are
    resolved on 1-minute bars so a stop order can be filled when price first
    trades through a level instead of waiting for a 5-minute close.
    """

    symbol: str = "NQ"
    point_value: float = 20.0          # E-mini NQ: $20 per index point
    tick_size: float = 0.25
    contracts: int = 1

    commission_per_side: float = 0.62  # $1.24 round turn per contract
    slippage_ticks: float = 1.0        # one tick on entry/stop/time exits
    stop_buffer_ticks: float = 1.0     # stop sits just beyond the 5m extreme

    london_start: time = time(4, 0)
    london_end: time = time(9, 0)
    entry_start: time = time(9, 30)
    entry_end: time = time(11, 0)
    exit_time: time = time(16, 0)

    target_r: float = 2.0
    # 1 = low/high of the last completed 5-minute bar before the entry.
    # Larger values use the lowest low / highest high of the last N bars.
    stop_lookback_bars: int = 1
    min_london_bars: int = 24          # skip holidays/half sessions

    # Research/default-book controls.  None preserves the original base book.
    range_cap_pct: float | None = None  # skip entries wider than this % of price
    mae_stop_quantile: float | None = None  # prior-month MAE percentile stop

    def __post_init__(self) -> None:
        if self.point_value <= 0 or self.tick_size <= 0:
            raise ValueError("point_value and tick_size must be positive")
        if self.contracts < 1:
            raise ValueError("contracts must be at least 1")
        if self.commission_per_side < 0 or self.slippage_ticks < 0:
            raise ValueError("costs cannot be negative")
        if self.stop_buffer_ticks < 0:
            raise ValueError("stop_buffer_ticks cannot be negative")
        if self.target_r <= 0:
            raise ValueError("target_r must be positive")
        if self.stop_lookback_bars < 1:
            raise ValueError("stop_lookback_bars must be at least 1")
        if self.range_cap_pct is not None and self.range_cap_pct <= 0:
            raise ValueError("range_cap_pct must be positive when set")
        if self.mae_stop_quantile is not None and not 0 < self.mae_stop_quantile < 1:
            raise ValueError("mae_stop_quantile must be between 0 and 1 when set")
        if not (self.london_start < self.london_end <= self.entry_start < self.entry_end):
            raise ValueError("session times must be chronological")
        if self.exit_time <= self.entry_start:
            raise ValueError("exit_time must be after the entry window")

    @property
    def tick_value(self) -> float:
        """Dollar value of one tick for the configured contract count."""
        return self.tick_size * self.point_value * self.contracts

    @property
    def commission(self) -> float:
        """Round-turn commission for the configured contract count."""
        return self.commission_per_side * 2 * self.contracts
