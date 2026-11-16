"""Pattern study for the SkyQ_NewLondon base trade ledger.

This is deliberately an in-sample diagnostic, not a new rule set.  It reports
group performance, permutation p-values, bootstrap confidence intervals, and
first/second-half consistency so an interesting slice is not mistaken for a
validated edge.

Examples:
    python scripts/analyze_patterns.py
    python scripts/analyze_patterns.py --calendar data/economic_calendar.csv
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skyq_newlondon.config import NY_TZ  # noqa: E402

DOW_ORDER = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
MONTH_ORDER = list(range(1, 13))
MONTH_NAMES = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]
TIME_LABELS = [
    "09:30-09:44",
    "09:45-09:59",
    "10:00-10:14",
    "10:15-10:29",
    "10:30-10:44",
    "10:45-10:59",
]
DOM_LABELS = ["1-5", "6-10", "11-15", "16-20", "21-25", "26-31"]
MAJOR_CODES = {"nfp", "cpi", "fomc"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--trades",
        type=Path,
        default=PROJECT_ROOT / "logs" / "nq_london_8y_trades.csv",
    )
    parser.add_argument(
        "--calendar",
        type=Path,
        default=PROJECT_ROOT / "data" / "economic_calendar.csv",
    )
    parser.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "logs")
    parser.add_argument("--label", default="nq_london_8y_patterns")
    parser.add_argument("--permutations", type=int, default=2000)
    parser.add_argument("--bootstraps", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=20261116)
    return parser.parse_args()


def _pf(net: pd.Series) -> float | None:
    wins = float(net[net > 0].sum())
    losses = float(-net[net < 0].sum())
    if losses == 0:
        return None
    return wins / losses


def _max_dd(net: pd.Series) -> float:
    if net.empty:
        return 0.0
    equity = net.cumsum()
    return float(-(equity - equity.cummax()).min())


def summarize(frame: pd.DataFrame) -> dict:
    if frame.empty:
        return {
            "trades": 0,
            "net_pnl": 0.0,
            "win_rate_pct": 0.0,
            "profit_factor": None,
            "expectancy": 0.0,
            "avg_r": 0.0,
            "max_drawdown": 0.0,
        }
    net = frame["net_pnl"].astype(float)
    return {
        "trades": int(len(frame)),
        "net_pnl": round(float(net.sum()), 2),
        "win_rate_pct": round(100.0 * float((net > 0).mean()), 2),
        "profit_factor": round(_pf(net), 3) if _pf(net) is not None else None,
        "expectancy": round(float(net.mean()), 2),
        "avg_r": round(float(frame["r_multiple"].mean()), 3),
        "max_drawdown": round(_max_dd(net), 2),
    }


def permutation_p(
    frame: pd.DataFrame,
    mask: pd.Series,
    permutations: int,
    rng: np.random.Generator,
) -> float:
    """Two-sided permutation p-value for the group-vs-rest mean net."""

    mask = mask.fillna(False).astype(bool)
    n_group = int(mask.sum())
    n_total = len(frame)
    if n_group == 0 or n_group == n_total or permutations <= 0:
        return float("nan")
    values = frame["net_pnl"].to_numpy(dtype=float)
    values = values[np.isfinite(values)]
    if len(values) != n_total:
        valid = np.isfinite(frame["net_pnl"].to_numpy(dtype=float))
        mask_values = mask.to_numpy(dtype=bool)[valid]
    else:
        mask_values = mask.to_numpy(dtype=bool)
    observed = values[mask_values].mean() - values[~mask_values].mean()
    count = 0
    for _ in range(permutations):
        shuffled = rng.permutation(mask_values)
        diff = values[shuffled].mean() - values[~shuffled].mean()
        if abs(diff) >= abs(observed):
            count += 1
    return (count + 1) / (permutations + 1)


def bootstrap_ci(
    frame: pd.DataFrame,
    bootstraps: int,
    rng: np.random.Generator,
) -> tuple[float, float]:
    values = frame["net_pnl"].to_numpy(dtype=float)
    if len(values) < 2 or bootstraps <= 0:
        return (float("nan"), float("nan"))
    samples = rng.choice(values, size=(bootstraps, len(values)), replace=True)
    means = samples.mean(axis=1)
    return (
        float(np.percentile(means, 2.5)),
        float(np.percentile(means, 97.5)),
    )


def half_stats(frame: pd.DataFrame) -> tuple[float, float]:
    first = frame[frame["entry_time"] < pd.Timestamp("2023-01-01", tz=NY_TZ)]
    second = frame[frame["entry_time"] >= pd.Timestamp("2023-01-01", tz=NY_TZ)]
    return (
        round(float(first["net_pnl"].sum()), 2) if not first.empty else 0.0,
        round(float(second["net_pnl"].sum()), 2) if not second.empty else 0.0,
    )


def group_table(
    frame: pd.DataFrame,
    by: str,
    label: str,
    permutations: int,
    bootstraps: int,
    rng: np.random.Generator,
    order: list | None = None,
) -> pd.DataFrame:
    rows = []
    groups = list(frame.groupby(by, observed=True, sort=False))
    n_groups = len(groups)
    for key, group in groups:
        stats = summarize(group)
        mask = frame[by].astype(object).eq(key)
        p = permutation_p(frame, mask, permutations, rng)
        ci_low, ci_high = bootstrap_ci(group, bootstraps, rng)
        first, second = half_stats(group)
        rows.append(
            {
                label: str(key),
                **stats,
                "p_perm": round(p, 4) if math.isfinite(p) else None,
                "p_bonferroni": round(min(1.0, p * n_groups), 4)
                if math.isfinite(p)
                else None,
                "mean_ci_low": round(ci_low, 2) if math.isfinite(ci_low) else None,
                "mean_ci_high": round(ci_high, 2) if math.isfinite(ci_high) else None,
                "first_half_net": first,
                "second_half_net": second,
                "consistent_halves": bool(first * second > 0),
            }
        )
    result = pd.DataFrame(rows)
    if order is not None and not result.empty:
        order_map = {str(value): i for i, value in enumerate(order)}
        result["_order"] = result[label].map(order_map).fillna(999)
        result = result.sort_values("_order").drop(columns="_order").reset_index(drop=True)
    return result


def add_calendar_flags(trades: pd.DataFrame, calendar: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    if calendar.empty:
        for column in ["major_event", "nfp", "cpi", "fomc", "preopen_major"]:
            trades[column] = False
        return trades, {"start": None, "end": None, "event_days": 0}

    cal = calendar.copy()
    cal["event_date"] = pd.to_datetime(cal["event_date"]).dt.normalize()
    cal["event_time_et"] = pd.to_timedelta(cal["event_time_et"].astype(str))
    cal["is_major"] = cal["event_code"].isin(MAJOR_CODES)
    cal["is_preopen_major"] = cal["is_major"] & (cal["event_time_et"] < pd.Timedelta("09:30:00"))

    flags = pd.DataFrame({"event_date": sorted(cal["event_date"].dropna().unique())})
    for code in ["nfp", "cpi", "fomc"]:
        dates = set(cal.loc[cal["event_code"] == code, "event_date"])
        flags[code] = flags["event_date"].isin(dates)
    major_dates = set(cal.loc[cal["is_major"], "event_date"])
    preopen_dates = set(cal.loc[cal["is_preopen_major"], "event_date"])
    flags["major_event"] = flags["event_date"].isin(major_dates)
    flags["preopen_major"] = flags["event_date"].isin(preopen_dates)

    merged = trades.merge(flags, left_on="day", right_on="event_date", how="left")
    for column in ["major_event", "nfp", "cpi", "fomc", "preopen_major"]:
        merged[column] = merged[column].fillna(False).astype(bool)

    info = {
        "start": cal["event_date"].min(),
        "end": cal["event_date"].max(),
        "event_days": int(cal["event_date"].nunique()),
        "nfp_days": int((cal["event_code"] == "nfp").sum()),
        "cpi_days": int((cal["event_code"] == "cpi").sum()),
        "fomc_days": int((cal["event_code"] == "fomc").sum()),
    }
    return merged, info


def prepare_trades(path: Path, calendar_path: Path) -> tuple[pd.DataFrame, dict]:
    frame = pd.read_csv(path)
    frame["entry_time"] = pd.to_datetime(
        frame["entry_time"], format="mixed", utc=True
    ).dt.tz_convert(NY_TZ)
    frame["exit_time"] = pd.to_datetime(
        frame["exit_time"], format="mixed", utc=True
    ).dt.tz_convert(NY_TZ)
    frame["day"] = pd.to_datetime(frame["day"]).dt.normalize()
    frame["year"] = frame["entry_time"].dt.year
    frame["month_num"] = frame["entry_time"].dt.month
    frame["month_name"] = frame["entry_time"].dt.month_name()
    frame["dow"] = frame["entry_time"].dt.day_name()
    frame["dow"] = pd.Categorical(frame["dow"], categories=DOW_ORDER, ordered=True)
    frame["entry_minute"] = frame["entry_time"].dt.hour * 60 + frame["entry_time"].dt.minute
    frame["time_bucket"] = pd.cut(
        frame["entry_minute"],
        bins=[570, 585, 600, 615, 630, 645, 660],
        labels=TIME_LABELS,
        right=False,
    )
    frame["day_of_month"] = frame["entry_time"].dt.day
    frame["dom_bucket"] = pd.cut(
        frame["day_of_month"],
        bins=[0, 5, 10, 15, 20, 25, 31],
        labels=DOM_LABELS,
        right=True,
    )
    frame["range_pct"] = (
        (frame["london_high"] - frame["london_low"]) / frame["entry_price"] * 100.0
    )

    # Calendar-structure proxies, independent of the macro-event file.
    frame["first_friday"] = (frame["dow"].astype(str) == "Friday") & (
        frame["day_of_month"] <= 7
    )
    frame["opex"] = (frame["dow"].astype(str) == "Friday") & frame[
        "day_of_month"
    ].between(15, 21)

    month_ends: set = set()
    quarter_ends: set = set()
    for period in sorted(frame["day"].dt.to_period("M").unique()):
        business_days = pd.bdate_range(period.start_time, period.end_time)
        last_three = {value.date() for value in business_days[-3:]}
        month_ends.update(last_three)
        if period.month in {3, 6, 9, 12}:
            quarter_ends.update(last_three)
    frame["month_end"] = frame["day"].dt.date.isin(month_ends)
    frame["quarter_end"] = frame["day"].dt.date.isin(quarter_ends)

    frame["event_group"] = np.where(
        frame["day"].dt.date.astype(str) >= "2019-05-10",
        "Covered period",
        "Pre-coverage",
    )

    calendar = pd.read_csv(calendar_path) if calendar_path.exists() else pd.DataFrame()
    frame, calendar_info = add_calendar_flags(frame, calendar)
    frame["is_event_covered"] = (
        (frame["day"] >= pd.Timestamp(calendar_info["start"]))
        & (frame["day"] <= pd.Timestamp(calendar_info["end"]))
        if calendar_info["start"] is not None
        else False
    )
    return frame, calendar_info


def event_sample(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["is_event_covered"]].copy()


def filter_table(
    frame: pd.DataFrame,
    event_frame: pd.DataFrame,
    permutations: int,
    bootstraps: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows = []

    def add(name: str, sample: pd.DataFrame, mask: pd.Series | None, note: str) -> None:
        mask = pd.Series(True, index=sample.index) if mask is None else mask
        selected = sample[mask.fillna(False).astype(bool)]
        stats = summarize(selected)
        first, second = half_stats(selected)
        rows.append(
            {
                "filter": name,
                "sample": note,
                **stats,
                "first_half_net": first,
                "second_half_net": second,
                "consistent_halves": bool(first * second > 0),
            }
        )

    add("Base — all trades", frame, None, "2018-10-23..2026-10-23")
    add(
        "Skip Friday",
        frame,
        frame["dow"].astype(str) != "Friday",
        "all trades",
    )
    add(
        "Skip Monday",
        frame,
        frame["dow"].astype(str) != "Monday",
        "all trades",
    )
    add(
        "Skip 10:00-10:59 entries",
        frame,
        frame["entry_minute"] < 600,
        "all trades",
    )
    add(
        "Skip range > 0.9%",
        frame,
        frame["range_pct"] <= 0.9,
        "all trades",
    )
    add("Long only", frame, frame["side"] == "long", "all trades")
    add("Short only", frame, frame["side"] == "short", "all trades")

    if not event_frame.empty:
        add(
            "Event sample base",
            event_frame,
            None,
            "2019-05-10..2026-10-14",
        )
        add(
            "Skip NFP/CPI/FOMC days",
            event_frame,
            ~event_frame["major_event"],
            "event-covered",
        )
        add(
            "Only NFP/CPI/FOMC days",
            event_frame,
            event_frame["major_event"],
            "event-covered",
        )
        add(
            "Skip NFP days",
            event_frame,
            ~event_frame["nfp"],
            "event-covered",
        )
        add(
            "Skip CPI days",
            event_frame,
            ~event_frame["cpi"],
            "event-covered",
        )
        add(
            "Skip FOMC days",
            event_frame,
            ~event_frame["fomc"],
            "event-covered",
        )
        add(
            "Skip pre-open NFP/CPI",
            event_frame,
            ~event_frame["preopen_major"],
            "event-covered",
        )

    add("Skip OpEx", frame, ~frame["opex"], "all trades")
    add("Skip month-end", frame, ~frame["month_end"], "all trades")
    return pd.DataFrame(rows)


def event_table(
    frame: pd.DataFrame,
    permutations: int,
    bootstraps: int,
    rng: np.random.Generator,
) -> pd.DataFrame:
    rows = []
    comparisons = [
        ("Any NFP/CPI/FOMC", "major_event"),
        ("NFP only", "nfp"),
        ("CPI only", "cpi"),
        ("FOMC only", "fomc"),
        ("Pre-open NFP/CPI", "preopen_major"),
    ]
    for name, column in comparisons:
        grouped = frame.assign(
            event_label=np.where(frame[column], "Event day", "No event")
        )
        for label, group in grouped.groupby("event_label", sort=False):
            stats = summarize(group)
            p = permutation_p(
                grouped,
                grouped["event_label"] == label,
                permutations,
                rng,
            )
            ci_low, ci_high = bootstrap_ci(group, bootstraps, rng)
            first, second = half_stats(group)
            rows.append(
                {
                    "comparison": name,
                    "group": label,
                    **stats,
                    "p_perm": round(p, 4) if math.isfinite(p) else None,
                    "mean_ci_low": round(ci_low, 2) if math.isfinite(ci_low) else None,
                    "mean_ci_high": round(ci_high, 2) if math.isfinite(ci_high) else None,
                    "first_half_net": first,
                    "second_half_net": second,
                    "consistent_halves": bool(first * second > 0),
                }
            )
    return pd.DataFrame(rows)


def monthly_table(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.copy()
    frame["month"] = frame["day"].dt.to_period("M").astype(str)
    rows = []
    for month, group in frame.groupby("month", sort=True):
        net = group["net_pnl"]
        rows.append(
            {
                "month": month,
                "trades": int(len(group)),
                "net_pnl": round(float(net.sum()), 2),
                "win_rate_pct": round(100.0 * float((net > 0).mean()), 2),
            }
        )
    return pd.DataFrame(rows)


def _table(frame: pd.DataFrame) -> str:
    return frame.to_string(index=False) if not frame.empty else "_No rows._"


def main() -> int:
    args = parse_args()
    rng = np.random.default_rng(args.seed)
    frame, calendar_info = prepare_trades(args.trades, args.calendar)
    events = event_sample(frame)

    dow = group_table(
        frame,
        "dow",
        "day_of_week",
        args.permutations,
        args.bootstraps,
        rng,
        order=DOW_ORDER,
    )
    month = group_table(
        frame,
        "month_name",
        "month",
        args.permutations,
        args.bootstraps,
        rng,
        order=MONTH_NAMES,
    )
    time_bucket = group_table(
        frame,
        "time_bucket",
        "entry_time",
        args.permutations,
        args.bootstraps,
        rng,
        order=TIME_LABELS,
    )
    dom = group_table(
        frame,
        "dom_bucket",
        "day_of_month",
        args.permutations,
        args.bootstraps,
        rng,
        order=DOM_LABELS,
    )
    other_calendar = group_table(
        frame.assign(
            opex_label=np.where(frame["opex"], "OpEx Friday", "Other day"),
            first_friday_label=np.where(
                frame["first_friday"], "First Friday", "Other day"
            ),
            month_end_label=np.where(frame["month_end"], "Month-end", "Other day"),
            quarter_end_label=np.where(
                frame["quarter_end"], "Quarter-end", "Other day"
            ),
        ),
        "opex_label",
        "calendar_pattern",
        args.permutations,
        args.bootstraps,
        rng,
    )
    # Append the other calendar slices as separate labeled rows.
    extra_rows = []
    for name, column in [
        ("First Friday", "first_friday_label"),
        ("Month-end", "month_end_label"),
        ("Quarter-end", "quarter_end_label"),
    ]:
        for label, group in frame.assign(
            group=np.where(
                frame[
                    {
                        "First Friday": "first_friday",
                        "Month-end": "month_end",
                        "Quarter-end": "quarter_end",
                    }[name]
                ],
                name,
                "Other day",
            )
        ).groupby("group", sort=False):
            stats = summarize(group)
            p = permutation_p(
                frame.assign(group=np.where(
                    frame[
                        {
                            "First Friday": "first_friday",
                            "Month-end": "month_end",
                            "Quarter-end": "quarter_end",
                        }[name]
                    ],
                    name,
                    "Other day",
                )),
                frame[
                    {
                        "First Friday": "first_friday",
                        "Month-end": "month_end",
                        "Quarter-end": "quarter_end",
                    }[name]
                ],
                args.permutations,
                rng,
            )
            first, second = half_stats(group)
            extra_rows.append(
                {
                    "calendar_pattern": name,
                    "group": label,
                    **stats,
                    "p_perm": round(p, 4) if math.isfinite(p) else None,
                    "p_bonferroni": round(min(1.0, p * 4), 4)
                    if math.isfinite(p)
                    else None,
                    "first_half_net": first,
                    "second_half_net": second,
                    "consistent_halves": bool(first * second > 0),
                }
            )
    extra = pd.DataFrame(extra_rows)
    other_calendar = other_calendar.rename(columns={"calendar_pattern": "group"})
    other_calendar["calendar_pattern"] = "OpEx"
    other_calendar = pd.concat([other_calendar, extra], ignore_index=True)

    events_table = event_table(events, args.permutations, args.bootstraps, rng)
    filters = filter_table(
        frame,
        events,
        args.permutations,
        args.bootstraps,
        rng,
    )
    monthly = monthly_table(frame)

    range_quartiles = frame.copy()
    range_quartiles["range_bucket"] = pd.qcut(
        range_quartiles["range_pct"],
        4,
        duplicates="drop",
    )
    range_table = group_table(
        range_quartiles,
        "range_bucket",
        "range_bucket",
        args.permutations,
        args.bootstraps,
        rng,
    )

    output = Path(args.out_dir)
    output.mkdir(parents=True, exist_ok=True)
    prefix = args.label
    paths = {
        "report": output / f"{prefix}.txt",
        "dow": output / f"{prefix}_dow.csv",
        "month": output / f"{prefix}_month.csv",
        "time": output / f"{prefix}_time.csv",
        "dom": output / f"{prefix}_dom.csv",
        "events": output / f"{prefix}_events.csv",
        "calendar": output / f"{prefix}_calendar.csv",
        "filters": output / f"{prefix}_filters.csv",
        "monthly": output / f"{prefix}_monthly.csv",
        "range": output / f"{prefix}_range.csv",
    }
    dow.to_csv(paths["dow"], index=False)
    month.to_csv(paths["month"], index=False)
    time_bucket.to_csv(paths["time"], index=False)
    dom.to_csv(paths["dom"], index=False)
    events_table.to_csv(paths["events"], index=False)
    other_calendar.to_csv(paths["calendar"], index=False)
    filters.to_csv(paths["filters"], index=False)
    monthly.to_csv(paths["monthly"], index=False)
    range_table.to_csv(paths["range"], index=False)

    candidates = []
    for table_name, table, group_column in [
        ("day of week", dow, "day_of_week"),
        ("month", month, "month"),
        ("entry time", time_bucket, "entry_time"),
        ("day of month", dom, "day_of_month"),
        ("range quartile", range_table, "range_bucket"),
    ]:
        for _, row in table.iterrows():
            if (
                row["p_bonferroni"] is not None
                and row["p_bonferroni"] < 0.05
                and row["trades"] >= 50
                and row["consistent_halves"]
            ):
                candidates.append(
                    {
                        "slice": table_name,
                        "group": row[group_column],
                        "trades": row["trades"],
                        "net_pnl": row["net_pnl"],
                        "p_bonferroni": row["p_bonferroni"],
                    }
                )

    positive_months = int((monthly["net_pnl"] > 0).sum()) if not monthly.empty else 0
    negative_months = int((monthly["net_pnl"] < 0).sum()) if not monthly.empty else 0
    best_month = monthly.loc[monthly["net_pnl"].idxmax()] if not monthly.empty else None
    worst_month = monthly.loc[monthly["net_pnl"].idxmin()] if not monthly.empty else None

    report = "\n".join(
        [
            "SkyQ_NewLondon — Pattern and Event Study",
            "=" * 62,
            f"Ledger: {args.trades}",
            f"Base trades: {len(frame):,} | {frame['day'].min().date()} to {frame['day'].max().date()}",
            f"Event coverage: {calendar_info['start']} to {calendar_info['end']} "
            f"({calendar_info['event_days']} event days)",
            f"Events: NFP {calendar_info['nfp_days']}, CPI {calendar_info['cpi_days']}, "
            f"FOMC {calendar_info['fomc_days']}",
            "",
            "IMPORTANT",
            "-" * 62,
            "Every table is in-sample.  p-values are permutation tests of the group",
            "mean versus the rest, not proof of a permanent edge.  Bonferroni-adjusted",
            "p-values are shown for the multi-category tables.  A slice is only a",
            "candidate if it has at least 50 trades and the same sign in both halves.",
            "",
            "Day of week",
            "-" * 62,
            _table(dow),
            "",
            "Month of year",
            "-" * 62,
            _table(month),
            "",
            "Entry time bucket (15 minutes)",
            "-" * 62,
            _table(time_bucket),
            "",
            "Day of month",
            "-" * 62,
            _table(dom),
            "",
            "Other calendar structure",
            "-" * 62,
            _table(other_calendar),
            "",
            "Major U.S. news days (event-covered sample)",
            "-" * 62,
            _table(events_table),
            "",
            "London range quartiles",
            "-" * 62,
            _table(range_table),
            "",
            "Filter simulations (in-sample)",
            "-" * 62,
            _table(filters),
            "",
            "Monthly consistency",
            "-" * 62,
            f"Positive months: {positive_months} | Negative months: {negative_months}",
            f"Best month: {best_month['month']} {best_month['net_pnl']:+.2f}"
            if best_month is not None
            else "Best month: n/a",
            f"Worst month: {worst_month['month']} {worst_month['net_pnl']:+.2f}"
            if worst_month is not None
            else "Worst month: n/a",
            "",
            "Candidate flags after the consistency/power screen",
            "-" * 62,
            _table(pd.DataFrame(candidates)) if candidates else "_None._",
            "",
            "News-data caveats",
            "-" * 62,
            "The macro schedule supplies CPI/NFP/FOMC dates and conventional release",
            "times (CPI/NFP 08:30 ET, FOMC 14:00 ET).  It covers 2019-05-10 onward.",
            "The raw Forex Factory cache had unreliable pre-2019 timestamps and is",
            "not used for the event study.  This is a major-event study, not a full",
            "economic-calendar event-window study.",
        ]
    )
    paths["report"].write_text(report, encoding="utf-8")
    print(report)
    print("\nSaved:")
    for name, path in paths.items():
        print(f"  {name:8s} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
