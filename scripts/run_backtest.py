"""Run the SkyQ_NewLondon NQ backtest.

The default is the researched best version: prior-month MAE q50 stop plus a
0.90% London-range cap.  Use ``--base`` to reproduce the original book.

Examples:
    python scripts/run_backtest.py                 # best/default
    python scripts/run_backtest.py --base          # original base book
    python scripts/run_backtest.py --start 2018-10-23 --end 2026-10-23
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from datetime import date, time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from skyq_newlondon.backtest import run_backtest  # noqa: E402
from skyq_newlondon.mae import run_best_backtest  # noqa: E402
from skyq_newlondon.config import (  # noqa: E402
    DEFAULT_END,
    DEFAULT_START,
    BookConfig,
)
from skyq_newlondon.data import load_1m  # noqa: E402
from skyq_newlondon.report import (  # noqa: E402
    compute_metrics,
    format_report,
    write_outputs,
)


def _date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected YYYY-MM-DD, got {value!r}") from exc


def _time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"expected HH:MM, got {value!r}") from exc


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        type=Path,
        default=PROJECT_ROOT / "data" / "nq_1m.parquet",
        help="1-minute NQ parquet (default: data/nq_1m.parquet)",
    )
    parser.add_argument("--start", type=_date, default=DEFAULT_START)
    parser.add_argument("--end", type=_date, default=DEFAULT_END)
    parser.add_argument("--contracts", type=int, default=1)
    parser.add_argument("--target-r", type=float, default=2.0)
    parser.add_argument(
        "--stop-lookback-bars",
        type=int,
        default=1,
        help="1 = last completed 5m bar (default); 3/5 = N-bar extreme",
    )
    parser.add_argument("--entry-end", type=_time, default=time(11, 0))
    parser.add_argument("--exit-time", type=_time, default=time(16, 0))
    parser.add_argument("--commission-per-side", type=float, default=0.62)
    parser.add_argument("--slippage-ticks", type=float, default=1.0)
    parser.add_argument("--stop-buffer-ticks", type=float, default=1.0)
    parser.add_argument("--min-london-bars", type=int, default=24)
    parser.add_argument(
        "--base",
        action="store_true",
        help="run the original prior-5m-bar-stop book instead of the best/default book",
    )
    parser.add_argument("--out-dir", type=Path, default=PROJECT_ROOT / "logs")
    parser.add_argument("--label", default=None)
    parser.add_argument("--no-write", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.start > args.end:
        raise SystemExit("--start must be on or before --end")

    config = replace(
        BookConfig(),
        contracts=args.contracts,
        target_r=args.target_r,
        stop_lookback_bars=args.stop_lookback_bars,
        entry_end=args.entry_end,
        exit_time=args.exit_time,
        commission_per_side=args.commission_per_side,
        slippage_ticks=args.slippage_ticks,
        stop_buffer_ticks=args.stop_buffer_ticks,
        min_london_bars=args.min_london_bars,
        range_cap_pct=None if args.base else 0.90,
        mae_stop_quantile=None if args.base else 0.50,
    )
    label = args.label or (
        "nq_london_base_8y" if args.base else "nq_london_best_mae_q50_range090"
    )

    bars = load_1m(args.data, start=args.start, end=args.end)
    print(
        f"Loaded {len(bars):,} 1-minute bars | "
        f"{bars.index.min()} to {bars.index.max()} | "
        f"{bars.index.tz}"
    )
    print(
        f"Mode: {'BASE' if args.base else 'BEST/DEFAULT (MAE q50 + 0.90% range cap)'}"
    )
    print(
        f"Rules: London {config.london_start:%H:%M}-{config.london_end:%H:%M} ET, "
        f"entry {config.entry_start:%H:%M}-{config.entry_end:%H:%M} ET, "
        f"{config.target_r:g}R, "
        f"{config.stop_lookback_bars}-bar base stop, "
        f"{config.stop_buffer_ticks:g}-tick buffer, "
        f"{config.exit_time:%H:%M} ET exit"
    )

    if args.base:
        result = run_backtest(bars, config=config, start=args.start, end=args.end)
    else:
        result = run_best_backtest(bars, config=config, start=args.start, end=args.end)
    metrics = compute_metrics(result.trades, result)
    print()
    print(format_report(result, metrics))

    if not args.no_write:
        paths = write_outputs(result, metrics, out_dir=args.out_dir, label=label)
        print()
        print("Saved:")
        for name, path in paths.items():
            print(f"  {name:8s} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
