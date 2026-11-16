# SkyQ_NewLondon — version comparison

All rows use NQ 1-minute data, 2018-10-23 through 2026-10-23, one contract,
$0.62/side commission, one tick of entry/stop/time slippage, and stop-first
same-bar treatment. Returns are backtest dollars, not live results.

| Variant | Role | Decision | Trades | Win % | Net P&L | PF | Max DD | Sharpe | Sortino | Avg stop | Target / stop / time |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Base book | Reference | Rejected as default | 1,955 | 36.37% | $-19,774.20 | 0.979 | $57,933.08 | -0.12 | -0.16 | 36.49 pts | 669 / 1221 / 65 |
| Range cap only | Research candidate | Superseded | 1,498 | 37.85% | $64,302.48 | 1.108 | $33,542.60 | 0.52 | 0.61 | 31.62 pts | 534 / 912 / 52 |
| MAE q50 (uncapped) | Stop study | Candidate, not default | 1,928 | 38.28% | $61,083.59 | 1.044 | $51,675.40 | 0.25 | 0.32 | 64.66 pts | 536 / 1106 / 286 |
| MAE q75 (uncapped) | Stop study | Rejected as default | 1,928 | 44.81% | $136,907.96 | 1.070 | $78,574.44 | 0.39 | 0.44 | 134.92 pts | 260 / 706 / 962 |
| MAE q90 (uncapped) | Stop study | Rejected as default | 1,928 | 48.76% | $167,195.23 | 1.077 | $90,823.04 | 0.41 | 0.44 | 221.52 pts | 94 / 370 / 1464 |
| MAE q95 (uncapped) | Stop study | Rejected as default | 1,928 | 49.74% | $168,568.32 | 1.076 | $90,875.13 | 0.40 | 0.41 | 281.38 pts | 46 / 255 / 1627 |
| MAE prior-month mean (uncapped) | Stop study | Rejected as default | 1,928 | 42.12% | $68,479.46 | 1.039 | $78,848.14 | 0.22 | 0.26 | 97.32 pts | 374 / 920 / 634 |
| MAE q50 + 0.90% range cap | DEFAULT | Selected | 1,343 | 38.12% | $97,430.51 | 1.130 | $35,184.30 | 0.59 | 0.67 | 50.38 pts | 403 / 773 / 167 |

## Decision notes

- **Base book** (Reference): Original rules. Loses after costs; retained behind `--base` for reproducibility.
- **Range cap only** (Research candidate): The 0.90% London-range cap alone improves the base, but the MAE q50 stop adds more.
- **MAE q50 (uncapped)** (Stop study): Improves the base, but is dominated by the capped q50 version.
- **MAE q75 (uncapped)** (Stop study): Wider stop increases drawdown and turns many trades into time exits.
- **MAE q90 (uncapped)** (Stop study): Wider stop increases drawdown and turns many trades into time exits.
- **MAE q95 (uncapped)** (Stop study): Wider stop increases drawdown and turns many trades into time exits.
- **MAE prior-month mean (uncapped)** (Stop study): The literal mean stop is wider, has a larger drawdown, and is heavily 2025-dependent.
- **MAE q50 + 0.90% range cap** (DEFAULT): Lowest drawdown among the improved variants, fewer time exits than q75+, and the best net/risk balance in-sample.

## Honest interpretation

- The default is the best **in-sample research** version, not a validated
  live system. It has a positive eight-year net, but 2026 is negative and
  the result is still dependent on 2021, 2023, and 2025.
- The base book is retained exactly as a reproducibility reference. It
  loses money after costs and must not be marketed as profitable.
- Wide stops can produce a larger nominal P&L while making most trades
  time exits. That is a different risk profile, not a free improvement.
- Before any live use: add a capped stop, walk-forward windows, contract
  roll handling, and a drawdown-aware position-size limit.
