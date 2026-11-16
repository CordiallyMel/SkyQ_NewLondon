"""Deterministic checks for the SkyQ New London rules."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date, time

import pandas as pd

from skyq_newlondon.backtest import run_backtest
from skyq_newlondon.config import BookConfig, NY_TZ
from skyq_newlondon.data import resample_5m
from skyq_newlondon.strategy import (
    build_entry,
    first_break,
    london_range,
    simulate_trade,
)


def make_day(
    day: date = date(2024, 1, 3),
    *,
    long_break: bool = True,
    short_break: bool = False,
    stop_hit: bool = False,
    both_levels: bool = False,
    gap_long: bool = False,
    no_break: bool = False,
) -> pd.DataFrame:
    """Build a complete 04:00-15:59 ET synthetic session.

    London range is 90-100.  The 09:00 bar is deliberately an outlier to prove
    that the 09:00-09:04 bar is outside the London range.
    """

    index = pd.date_range(
        f"{day.isoformat()} 04:00",
        f"{day.isoformat()} 15:59",
        freq="1min",
        tz=NY_TZ,
    )
    bars = pd.DataFrame(
        {
            "open": 95.0,
            "high": 95.0,
            "low": 95.0,
            "close": 95.0,
        },
        index=index,
    )
    times = index.time

    london = (times >= time(4, 0)) & (times < time(9, 0))
    bars.loc[london, ["open", "close"]] = 95.0
    bars.loc[london, "high"] = 100.0
    bars.loc[london, "low"] = 90.0

    # Outlier outside the London window.
    bars.loc[times == time(9, 0), "high"] = 200.0
    bars.loc[times == time(9, 0), "low"] = 80.0

    # The last completed 5m bar before a 09:30 entry has a 95 low and 98 high.
    prior = (times >= time(9, 25)) & (times < time(9, 30))
    bars.loc[prior, ["open", "close"]] = 97.0
    bars.loc[prior, "high"] = 98.0
    bars.loc[prior, "low"] = 95.0

    bars.loc[times >= time(9, 31), ["open", "high", "low", "close"]] = 100.0

    if no_break:
        bars.loc[times == time(9, 0), "high"] = 101.0
        bars.loc[times >= time(9, 31), ["open", "high", "low", "close"]] = 95.0
        return bars

    if both_levels:
        bars.loc[times == time(9, 30), ["open", "high", "low", "close"]] = [
            91.0,
            101.0,
            89.0,
            90.0,
        ]
    elif gap_long:
        bars.loc[times == time(9, 30), ["open", "high", "low", "close"]] = [
            102.0,
            103.0,
            101.0,
            102.5,
        ]
    elif short_break:
        bars.loc[times == time(9, 30), ["open", "high", "low", "close"]] = [
            91.0,
            91.0,
            89.0,
            90.0,
        ]
        bars.loc[times == time(9, 31), ["open", "high", "low", "close"]] = [
            90.0,
            90.0,
            73.0,
            74.0,
        ]
    elif long_break:
        bars.loc[times == time(9, 30), ["open", "high", "low", "close"]] = [
            99.0,
            101.0,
            98.0,
            100.5,
        ]

    if stop_hit:
        bars.loc[times == time(9, 31), ["open", "high", "low", "close"]] = [
            96.0,
            99.0,
            94.0,
            95.0,
        ]
    elif long_break and not short_break and not both_levels:
        bars.loc[times == time(9, 31), ["open", "high", "low", "close"]] = [
            100.5,
            111.0,
            100.0,
            110.0,
        ]

    # A quiet afternoon for the time-exit test.
    afternoon = times >= time(9, 32)
    bars.loc[afternoon, ["open", "close"]] = 100.0
    bars.loc[afternoon, "high"] = 103.0
    bars.loc[afternoon, "low"] = 99.0
    bars.loc[times == time(15, 59), ["open", "high", "low", "close"]] = [
        101.0,
        103.0,
        99.0,
        102.0,
    ]
    return bars


class LondonRulesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = replace(
            BookConfig(),
            commission_per_side=0.0,
            slippage_ticks=0.0,
            stop_buffer_ticks=0.0,
            min_london_bars=1,
        )

    def frames(self, **kwargs):
        bars_1m = make_day(**kwargs)
        bars_5m = resample_5m(bars_1m)
        return bars_1m, bars_5m

    def test_london_range_uses_only_0400_to_0900(self) -> None:
        _, bars_5m = self.frames()
        result = london_range(bars_5m, self.config)
        self.assertIsNotNone(result)
        self.assertEqual(result.high, 100.0)
        self.assertEqual(result.low, 90.0)
        self.assertEqual(result.bars, 60)

    def test_long_breakout_uses_2r_target(self) -> None:
        bars_1m, bars_5m = self.frames(long_break=True)
        london = london_range(bars_5m, self.config)
        signal = first_break(bars_1m, london, self.config)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.side, "long")
        self.assertEqual(signal.raw_entry, 100.0)

        entry = build_entry(bars_5m, signal, london, self.config)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.stop_price, 95.0)
        self.assertEqual(entry.risk_points, 5.0)
        self.assertEqual(entry.target_price, 110.0)

        trade = simulate_trade(entry, bars_1m, self.config)
        self.assertEqual(trade.exit_reason, "target")
        self.assertEqual(trade.exit_price, 110.0)
        self.assertAlmostEqual(trade.r_multiple, 2.0, places=6)

    def test_short_breakout_uses_2r_target(self) -> None:
        bars_1m, bars_5m = self.frames(long_break=False, short_break=True)
        london = london_range(bars_5m, self.config)
        signal = first_break(bars_1m, london, self.config)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.side, "short")
        self.assertEqual(signal.raw_entry, 90.0)

        entry = build_entry(bars_5m, signal, london, self.config)
        self.assertIsNotNone(entry)
        # The prior 5m bar is 95 low / 98 high; a short stops above its high.
        self.assertEqual(entry.stop_price, 98.0)
        self.assertEqual(entry.target_price, 74.0)

        trade = simulate_trade(entry, bars_1m, self.config)
        self.assertEqual(trade.exit_reason, "target")
        self.assertEqual(trade.exit_price, 74.0)
        self.assertAlmostEqual(trade.r_multiple, 2.0, places=6)

    def test_stop_uses_prior_completed_bar_not_breakout_bar(self) -> None:
        bars_1m, bars_5m = self.frames(long_break=True, stop_hit=True)
        london = london_range(bars_5m, self.config)
        signal = first_break(bars_1m, london, self.config)
        entry = build_entry(bars_5m, signal, london, self.config)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.stop_price, 95.0)
        self.assertEqual(entry.prior_bar_time.time(), time(9, 25))
        trade = simulate_trade(entry, bars_1m, self.config)
        self.assertEqual(trade.exit_reason, "stop")
        self.assertEqual(trade.exit_price, 95.0)
        self.assertAlmostEqual(trade.r_multiple, -1.0, places=6)

    def test_stop_lookback_three_uses_wider_extreme(self) -> None:
        bars_1m = make_day(long_break=True)
        bars_5m = resample_5m(bars_1m)
        # Make the 09:15 and 09:20 lows lower than the 09:25 low.
        for timestamp, low in [("09:15", 93.0), ("09:20", 94.0)]:
            times = bars_5m.index.time
            mask = times >= time(int(timestamp[:2]), int(timestamp[3:]))
            # Use the 5m bucket containing that minute.
            target = pd.Timestamp(f"2024-01-03 {timestamp}:00", tz=NY_TZ)
            bucket = bars_5m.index[bars_5m.index == target]
            if len(bucket):
                bars_5m.loc[bucket, "low"] = low
        config = replace(self.config, stop_lookback_bars=3)
        london = london_range(bars_5m, config)
        signal = first_break(bars_1m, london, config)
        entry = build_entry(bars_5m, signal, london, config)
        self.assertIsNotNone(entry)
        self.assertEqual(entry.stop_price, 93.0)

    def test_pre_0930_break_does_not_count(self) -> None:
        bars_1m, bars_5m = self.frames(no_break=True)
        london = london_range(bars_5m, self.config)
        self.assertIsNone(first_break(bars_1m, london, self.config))

    def test_one_trade_per_day_and_first_side_wins(self) -> None:
        bars_1m = make_day(long_break=False, short_break=True)
        # Add a long break after the short entry; it must be ignored.
        bars_1m.loc[
            bars_1m.index.time == time(9, 31),
            ["open", "high", "low", "close"],
        ] = [90.0, 101.0, 89.0, 95.0]
        result = run_backtest(
            bars_1m,
            config=self.config,
            start=date(2024, 1, 3),
            end=date(2024, 1, 3),
        )
        self.assertEqual(len(result.trades), 1)
        self.assertEqual(result.trades.iloc[0]["side"], "short")

    def test_time_exit_is_used_when_neither_bracket_hits(self) -> None:
        bars_1m, bars_5m = self.frames(long_break=True)
        # Remove the 09:31 target spike.
        bars_1m.loc[
            bars_1m.index.time == time(9, 31),
            ["open", "high", "low", "close"],
        ] = [100.5, 101.0, 99.0, 100.5]
        london = london_range(bars_5m, self.config)
        signal = first_break(bars_1m, london, self.config)
        entry = build_entry(bars_5m, signal, london, self.config)
        trade = simulate_trade(entry, bars_1m, self.config)
        self.assertEqual(trade.exit_reason, "time")
        self.assertEqual(trade.exit_time.time(), time(15, 59))
        self.assertEqual(trade.exit_price, 102.0)

    def test_one_huge_minute_uses_the_closer_level(self) -> None:
        bars_1m, bars_5m = self.frames(both_levels=True)
        london = london_range(bars_5m, self.config)
        signal = first_break(bars_1m, london, self.config)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.side, "short")

    def test_gap_through_level_fills_at_open(self) -> None:
        bars_1m, bars_5m = self.frames(gap_long=True)
        london = london_range(bars_5m, self.config)
        signal = first_break(bars_1m, london, self.config)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.side, "long")
        self.assertEqual(signal.raw_entry, 102.0)
        entry = build_entry(bars_5m, signal, london, self.config)
        self.assertEqual(entry.entry_price, 102.0)
        self.assertEqual(entry.stop_price, 95.0)
        self.assertEqual(entry.target_price, 116.0)

    def test_range_cap_skips_wide_london_range(self) -> None:
        bars_1m = make_day(long_break=True)
        tight = replace(self.config, range_cap_pct=1.0)
        skipped = run_backtest(
            bars_1m,
            config=tight,
            start=date(2024, 1, 3),
            end=date(2024, 1, 3),
        )
        self.assertEqual(len(skipped.trades), 0)
        self.assertEqual(skipped.range_capped, 1)

        wide = replace(self.config, range_cap_pct=20.0)
        kept = run_backtest(
            bars_1m,
            config=wide,
            start=date(2024, 1, 3),
            end=date(2024, 1, 3),
        )
        self.assertEqual(len(kept.trades), 1)
        self.assertEqual(kept.range_capped, 0)

    def test_costs_and_buffer_are_in_the_fill(self) -> None:
        config = replace(BookConfig(), min_london_bars=1)
        bars_1m, bars_5m = self.frames(long_break=True)
        bars_1m.loc[
            bars_1m.index.time == time(9, 31),
            ["open", "high", "low", "close"],
        ] = [100.5, 112.0, 100.0, 111.0]
        london = london_range(bars_5m, config)
        signal = first_break(bars_1m, london, config)
        entry = build_entry(bars_5m, signal, london, config)
        self.assertAlmostEqual(entry.entry_price, 100.25)
        self.assertAlmostEqual(entry.stop_price, 94.75)
        self.assertAlmostEqual(entry.risk_points, 5.5)
        self.assertAlmostEqual(entry.target_price, 111.25)
        trade = simulate_trade(entry, bars_1m, config)
        self.assertEqual(trade.exit_reason, "target")
        self.assertAlmostEqual(trade.gross_pnl, 220.0)
        self.assertAlmostEqual(trade.net_pnl, 218.76)
        self.assertAlmostEqual(trade.r_multiple, 1.988727, places=6)


if __name__ == "__main__":
    unittest.main()
