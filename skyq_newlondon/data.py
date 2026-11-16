"""Data loading and resampling for SkyQ_NewLondon."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Union

import pandas as pd

from .config import NY_TZ

DateLike = Union[str, date, datetime, pd.Timestamp]
OHLC = ["open", "high", "low", "close"]


def _timestamp(value: DateLike, tz: str) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        return ts.tz_localize(tz)
    return ts.tz_convert(tz)


def load_1m(
    path: str | Path,
    start: DateLike | None = None,
    end: DateLike | None = None,
    tz: str = NY_TZ,
) -> pd.DataFrame:
    """Load 1-minute OHLCV bars and return them in New York time.

    ``start`` and ``end`` are inclusive calendar dates.  Passing a timestamp
    instead uses that exact timestamp.
    """

    frame = pd.read_parquet(path)
    if not isinstance(frame.index, pd.DatetimeIndex):
        if "time" not in frame.columns:
            raise ValueError("parquet must have a DatetimeIndex or a 'time' column")
        frame = frame.set_index("time")

    index = pd.DatetimeIndex(frame.index)
    index = index.tz_localize(tz) if index.tz is None else index.tz_convert(tz)
    frame.index = index
    frame = frame.sort_index()
    frame = frame[~frame.index.duplicated(keep="last")]

    missing = [column for column in OHLC if column not in frame.columns]
    if missing:
        raise ValueError(f"data is missing required columns: {missing}")
    frame = frame[OHLC].astype(float)

    if start is not None:
        start_ts = _timestamp(start, tz)
        if isinstance(start, (date, datetime)) and not isinstance(start, pd.Timestamp):
            start_ts = start_ts.normalize()
        frame = frame[frame.index >= start_ts]

    if end is not None:
        end_ts = _timestamp(end, tz)
        if isinstance(end, (date, datetime)) and not isinstance(end, pd.Timestamp):
            end_ts = end_ts.normalize() + pd.Timedelta(days=1)
        frame = frame[frame.index < end_ts]

    if frame.empty:
        raise ValueError("no bars remain after applying the requested date range")
    return frame


def resample_5m(bars_1m: pd.DataFrame) -> pd.DataFrame:
    """Build left-labelled 5-minute OHLC bars from 1-minute bars."""

    if bars_1m.empty:
        return bars_1m.copy()
    five = bars_1m.resample(
        "5min",
        origin="start_day",
        label="left",
        closed="left",
    ).agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
        }
    )
    return five.dropna(subset=OHLC)


def group_by_day(frame: pd.DataFrame) -> dict[date, pd.DataFrame]:
    """Split a timezone-aware frame into calendar-day frames."""

    if frame.empty:
        return {}
    return {
        pd.Timestamp(day).date(): group
        for day, group in frame.groupby(frame.index.date, sort=True)
    }
