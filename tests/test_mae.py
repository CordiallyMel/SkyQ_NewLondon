"""Tests for the truncated-MAE research layer."""

from __future__ import annotations

import unittest
from dataclasses import replace
from datetime import date

import pandas as pd

from skyq_newlondon.config import BookConfig, NY_TZ
from skyq_newlondon.mae import (
    make_mae_stop_entry,
    measure_truncated_mae,
    monthly_mae_quantiles,
)
from skyq_newlondon.strategy import Entry


def make_entry(side: str = "long") -> Entry:
    return Entry(
        day=date(2024, 1, 3),
        side=side,
        entry_time=pd.Timestamp("2024-01-03 09:30:00", tz=NY_TZ),
        raw_entry=100.0,
        entry_price=100.0,
        stop_price=95.0 if side == "long" else 105.0,
        target_price=110.0 if side == "long" else 90.0,
        risk_points=5.0,
        risk_dollars=100.0,
        london_high=100.0,
        london_low=90.0,
        prior_bar_time=pd.Timestamp("2024-01-03 09:25:00", tz=NY_TZ),
        prior_extreme=95.0 if side == "long" else 105.0,
        entry_slippage_points=0.0,
    )


def make_day(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    index = pd.DatetimeIndex(
        [pd.Timestamp(f"2024-01-03 {time}:00", tz=NY_TZ) for time, *_ in rows]
    )
    return pd.DataFrame(
        {
            "open": [row[1] for row in rows],
            "high": [row[2] for row in rows],
            "low": [row[3] for row in rows],
            "close": [row[4] for row in rows],
        },
        index=index,
    )


class MaeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.config = replace(
            BookConfig(),
            commission_per_side=0.0,
            slippage_ticks=0.0,
            stop_buffer_ticks=0.0,
        )

    def test_mae_truncates_when_target_is_touched(self) -> None:
        entry = make_entry("long")
        # 09:31 is +5 adverse; 09:32 touches the 110 target; 09:33 is a crash
        # after the trade would already have been closed and must be ignored.
        day = make_day(
            [
                ("09:31", 100.0, 101.0, 95.0, 100.0),
                ("09:32", 100.0, 111.0, 99.0, 110.0),
                ("09:33", 110.0, 110.0, 50.0, 50.0),
            ]
        )
        obs = measure_truncated_mae(entry, day, self.config)
        self.assertTrue(obs.target_hit)
        self.assertEqual(obs.bars, 2)
        self.assertAlmostEqual(obs.mae_points, 5.0)
        self.assertAlmostEqual(obs.mae_pct_range, 50.0)

    def test_mae_is_measured_at_session_end_without_target(self) -> None:
        entry = make_entry("long")
        day = make_day(
            [
                ("09:31", 100.0, 101.0, 95.0, 100.0),
                ("15:59", 100.0, 101.0, 94.0, 100.0),
            ]
        )
        obs = measure_truncated_mae(entry, day, self.config)
        self.assertFalse(obs.target_hit)
        self.assertAlmostEqual(obs.mae_points, 6.0)
        self.assertAlmostEqual(obs.mae_pct_range, 60.0)

    def test_short_mae_uses_adverse_high(self) -> None:
        entry = make_entry("short")
        day = make_day(
            [
                ("09:31", 100.0, 110.0, 100.0, 105.0),
                ("09:32", 100.0, 105.0, 89.0, 90.0),
                ("09:33", 90.0, 90.0, 50.0, 50.0),
            ]
        )
        obs = measure_truncated_mae(entry, day, self.config)
        self.assertTrue(obs.target_hit)
        self.assertAlmostEqual(obs.mae_points, 10.0)
        self.assertAlmostEqual(obs.mae_pct_range, 100.0)

    def test_mae_stop_keeps_2r_target(self) -> None:
        entry = make_entry("long")
        adjusted = make_mae_stop_entry(entry, 50.0, self.config)
        self.assertIsNotNone(adjusted)
        self.assertAlmostEqual(adjusted.stop_price, 95.0)
        self.assertAlmostEqual(adjusted.target_price, 110.0)
        self.assertAlmostEqual(adjusted.risk_points, 5.0)

    def test_short_mae_stop_is_above_entry(self) -> None:
        entry = make_entry("short")
        adjusted = make_mae_stop_entry(entry, 50.0, self.config)
        self.assertIsNotNone(adjusted)
        self.assertAlmostEqual(adjusted.stop_price, 105.0)
        self.assertAlmostEqual(adjusted.target_price, 90.0)
        self.assertAlmostEqual(adjusted.risk_points, 5.0)

    def test_monthly_quantiles_are_per_month(self) -> None:
        frame = pd.DataFrame(
            {
                "month": ["2019-01", "2019-01", "2019-01", "2019-02"],
                "mae_pct_range": [10.0, 20.0, 30.0, 90.0],
            }
        )
        stats = monthly_mae_quantiles(frame, 0.5)
        jan = stats.loc[stats["month"] == "2019-01"].iloc[0]
        feb = stats.loc[stats["month"] == "2019-02"].iloc[0]
        self.assertEqual(int(jan["count"]), 3)
        self.assertEqual(int(feb["count"]), 1)
        self.assertAlmostEqual(jan["quantile"], 20.0)
        self.assertAlmostEqual(feb["quantile"], 90.0)


if __name__ == "__main__":
    unittest.main()
