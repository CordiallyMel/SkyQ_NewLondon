# SkyQ_NewLondon

**NQ London/NY crossover breakout book — research backtest, not a live system.**

The **default** is now the researched best in-sample version:

> **Prior-month MAE q50 stop + London-range cap of 0.90% of entry price.**

The original book is still fully reproducible with `--base`. It is retained as
a control, not because it is profitable. The base book lost money after costs.

There is no broker connection, order router, live runner, dashboard, or
watchdog in this repository.

**Companion SQL project:**
<https://github.com/CordiallyMel/nq-market-postgres> — the same NQ one-minute
source loaded into PostgreSQL with CTEs, window functions, data-quality checks,
and a separate range-capped analytics model.

---

## Default strategy rules

1. **Instrument:** NQ, one contract, $20 per index point.
2. **London range:** high and low of 04:00–08:59 ET on 5-minute bars. The 09:00
   bar is excluded.
3. **Range filter:** skip the session when
   `(London high − London low) / entry price × 100 > 0.90`.
4. **Entry window:** stop orders at the London high/low, 09:30–10:59 ET. The
   first side to trade is the day's only trade.
5. **Stop:** prior-month 50th-percentile truncated MAE, expressed as a
   percentage of the current London range, plus one tick. The MAE measurement
   stops when the base 2R target is touched, so heat after a trade would have
   closed is excluded.
6. **Target:** 2R from the actual entry and MAE stop, rounded to the nearest NQ
   tick.
7. **One trade per day:** no second side, no re-entry.
8. **Time exit:** flat at 16:00 ET. No overnight risk.

The 0.90% filter is applied **before** the prior-month MAE statistics are
built. Wide-range sessions therefore do not influence the stop used in the book.

### Execution assumptions

- Stop-entry fills occur when price first trades through the level.
- A gap through a level fills at the 1-minute open plus adverse slippage.
- If one minute trades through both London levels, the side closer to that
  minute's open is treated as first.
- Exits begin on the minute after entry.
- If a later minute contains both stop and target, **stop is assumed first**.
- Stop and time exits pay one tick of slippage; target exits are modeled as
  limit fills.
- Commission is $0.62/side ($1.24 round turn).
- Continuous NQ data; quarterly roll gaps are not separately modeled.

---

## Default result — 2018-10-23 through 2026-10-23

**In-sample research result. Not a live track record.**

| Metric | Default book |
|---|---:|
| Trades | **1,343** (732 long / 611 short) |
| Trades per year | 167.9 |
| Win rate | **38.12%** |
| Net P&L | **+$97,430.51** (+4,871.53 NQ points) |
| Net per month / year | +$1,202.85 / +$12,178.81 |
| Profit factor | **1.130** |
| Expectancy per trade | +$72.55 |
| Average R | +0.065R |
| Average win / average loss | +$1,659.11 / −$904.98 |
| Reward/risk (avg win ÷ avg loss) | **1.833** |
| Break-even win rate | **35.29%** (actual 38.12%, cushion +2.83 pts) |
| Max drawdown | **$35,184.30** |
| Max consecutive losses | 14 |
| Sharpe (daily, annualized) | **0.59** |
| Sortino (daily, annualized) | **0.67** |
| Average stop | 50.38 NQ points |
| Average planned risk | $1,007.53 |
| p90 / largest planned risk | $2,080.30 / $4,484.18 |
| Worst trade / best trade | −$4,094.87 / +$6,403.76 |
| Worst month | −$17,703.65 |
| Positive months / losing months | **48 / 33** (81 months) |
| Positive years / losing years | **5 / 4** |
| Reached +1R / +2R at any point | 48.9% / 29.3% |
| Target / stop / time exits | 403 / 773 / 167 |
| Commission + slippage | $13,080.32 |
| P&L before commission | $99,095.83 |
| P&L before commission and slippage | $110,510.83 |
| Sessions scanned | 2,066 |
| London ranges built | 2,060 |
| No-break sessions | 105 |
| Sessions skipped by 0.90% cap | **457** |

### Year by year

| Year | Trades | Win rate | Net P&L | Profit factor | Max DD |
|---:|---:|---:|---:|---:|---:|
| 2018* | 7 | 14.29% | −$3,726.18 | 0.080 | $4,049.94 |
| 2019 | 202 | 38.12% | +$4,122.50 | 1.099 | $6,356.72 |
| 2020 | 128 | 39.06% | +$1,346.82 | 1.026 | $11,561.25 |
| 2021 | 208 | 38.94% | +$21,222.05 | 1.228 | $19,921.40 |
| 2022 | 46 | 39.13% | −$1,207.85 | 0.949 | $10,944.49 |
| 2023 | 210 | 39.52% | +$24,243.39 | 1.221 | $17,254.19 |
| 2024 | 213 | 36.62% | −$527.67 | 0.996 | $23,415.84 |
| 2025 | 187 | 40.11% | +$55,464.66 | 1.433 | $21,857.16 |
| 2026* | 142 | 34.51% | −$3,507.19 | 0.978 | $35,184.30 |

\* Partial year. 2018 starts 2018-10-23; 2026 ends 2026-10-23.

**The default is not a smooth curve.** 2021, 2023, and especially 2025 carry
the result; 2022, 2024, and 2026 are negative. The $35.2k drawdown occurs in
the most recent partial year. This is a research candidate, not evidence of a
durable live edge.

### By side and exit

| Side | Trades | Win rate | Net P&L | PF | Average R |
|---|---:|---:|---:|---:|---:|
| Long | 732 | 38.80% | +$71,517.96 | 1.181 | +0.068R |
| Short | 611 | 37.32% | +$25,912.55 | 1.073 | +0.061R |

| Exit | Trades | Win rate | Net P&L | Average R |
|---|---:|---:|---:|---:|
| Target | 403 | 100.00% | +$687,300.28 | +1.997R |
| Stop | 773 | 0.00% | −$722,087.69 | −1.023R |
| Time | 167 | 65.27% | +$132,217.92 | +0.438R |

Both sides are positive in the default, unlike the base book. That does not
remove the yearly instability: the short side is positive overall but was
negative in 2024 and 2026.

---

## Version comparison — including failed versions

All rows use the same data, one NQ contract, the same costs, and stop-first
same-bar treatment. **Sharpe and Sortino are daily and annualized.** The table
is also in [`logs/nq_london_version_comparison.md`](logs/nq_london_version_comparison.md)
and [`FAILED_VERSIONS.md`](FAILED_VERSIONS.md).

| Variant | Status | Trades | Win % | Net P&L | PF | Max DD | Sharpe | Sortino | Avg stop | Target / stop / time |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **MAE q50 + 0.90% cap** | **DEFAULT** | **1,343** | **38.12%** | **+$97,430.51** | **1.130** | **$35,184.30** | **0.59** | **0.67** | **50.38 pts** | **403 / 773 / 167** |
| Range cap only | Superseded | 1,498 | 37.85% | +$64,302.48 | 1.108 | $33,542.60 | 0.52 | 0.61 | 31.62 pts | 534 / 912 / 52 |
| MAE q50, uncapped | Candidate, not default | 1,928 | 38.28% | +$61,083.59 | 1.044 | $51,675.40 | 0.25 | 0.32 | 64.66 pts | 536 / 1,106 / 286 |
| MAE q75, uncapped | Rejected | 1,928 | 44.81% | +$136,907.96 | 1.070 | $78,574.44 | 0.39 | 0.44 | 134.92 pts | 260 / 706 / 962 |
| MAE q90, uncapped | Rejected | 1,928 | 48.76% | +$167,195.23 | 1.077 | $90,823.04 | 0.41 | 0.44 | 221.52 pts | 94 / 370 / 1,464 |
| MAE q95, uncapped | Rejected | 1,928 | 49.74% | +$168,568.32 | 1.076 | $90,875.13 | 0.40 | 0.41 | 281.38 pts | 46 / 255 / 1,627 |
| MAE prior-month mean, uncapped | Rejected | 1,928 | 42.12% | +$68,479.46 | 1.039 | $78,848.14 | 0.22 | 0.26 | 97.32 pts | 374 / 920 / 634 |
| **Base book** | **Control / rejected** | **1,955** | **36.37%** | **−$19,774.20** | **0.979** | **$57,933.08** | **−0.12** | **−0.16** | **36.49 pts** | **669 / 1,221 / 65** |

### Why the default won

- It has the **highest Sharpe and Sortino** of the improved variants and the
  **lowest drawdown** ($35.2k versus $51.7k–$90.9k).
- It keeps a sensible **2R target** and a 50-point average stop. q75/q90/q95
  widen the stop to 135–281 points and turn 50–84% of trades into time exits.
- It is **not** the highest nominal P&L. q90/q95 print +$167k/+$169k, but with
  $90.8k drawdowns and a fundamentally different hold-to-close profile. Those
  are rejected as defaults, not presented as superior books.

### Why the base is retained

The base book is the original hypothesis and the control. It produced
**−$19,774.20**, PF **0.979**, and a **$57,933.08** drawdown over 1,955 trades.
It is reproducible with:

```powershell
..\SkyQ_Scan\.venv\Scripts\python.exe scripts/run_backtest.py --base
```

Do not describe the base as profitable, validated, or deployable. It is not.

---

## What was researched

The full pattern/news/MAE study is in [`RESEARCH.md`](RESEARCH.md). The short
version:

- **Day of week:** no usable filter; all Bonferroni-adjusted p-values were 1.0.
- **Major NFP/CPI/FOMC news:** no measurable edge or penalty (p ≈ 0.87).
- **April:** +$50,647 in the base sample, but concentrated in wide ranges and
  2025. Secondary hypothesis, not a live filter.
- **Month-end:** +$46,600 raw, but does not survive a four-test correction and
  is not additive with the range filter.
- **Wide London ranges:** the strongest broad pattern. The top quartile lost
  $88,311; a 0.90% cap alone made +$64,302 with a $33,543 drawdown.
- **MAE stops:** q50 is the only useful percentile. q75/q90/q95 buy nominal
  P&L with much wider stops, larger drawdowns, and mostly time exits.
- **Default combination:** q50 + 0.90% cap, with the cap applied before the MAE
  statistics are computed.

**Every result here is in-sample.** The default has not passed a rolling
walk-forward test, a paper-trading period, or a live fill audit. The 2026
partial year is negative. Treat it as a research candidate and a portfolio
artifact, not a trading recommendation.

---

## Reproduce it

From this folder:

```powershell
# Default: MAE q50 + 0.90% range cap
..\SkyQ_Scan\.venv\Scripts\python.exe scripts/run_backtest.py

# Original base book (control)
..\SkyQ_Scan\.venv\Scripts\python.exe scripts/run_backtest.py --base

# Rebuild the full failed-version table
..\SkyQ_Scan\.venv\Scripts\python.exe scripts/build_version_comparison.py

# Deterministic tests (18)
..\SkyQ_Scan\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

With a normal local environment:

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python scripts/run_backtest.py
```

`run_backtest.ps1` uses `$env:PYTHON`, a local `.venv`, the workspace
interpreter, or `python`, in that order.

Research commands:

```powershell
..\SkyQ_Scan\.venv\Scripts\python.exe scripts/analyze_patterns.py
..\SkyQ_Scan\.venv\Scripts\python.exe scripts/run_mae_stop.py
..\SkyQ_Scan\.venv\Scripts\python.exe scripts/run_mae_stop.py --include-mean
```

---

## Data and window

- Source: `data/nq_1m.parquet` (56 MB; **not committed** to keep the repository light)
- The best ledger, summary, reports, and failed-version table are committed under `logs/`
- 3,350,033 one-minute bars total, 2017-04-02 through 2026-10-23
- Timezone: `America/New_York`
- Headline window: **2018-10-23 through 2026-10-23** — exactly 8.00 calendar years
- 2,811,231 one-minute bars in the test window
- 2,066 weekday sessions scanned
- 2,060 London ranges built
- 105 no-break sessions
- 1,955 base entries before the cap
- 457 entries removed by the 0.90% range cap
- 155 additional entries skipped because prior-month MAE history was unavailable
- 1,343 trades in the default book
- Major-event calendar: `data/economic_calendar.csv` — 250 NFP/CPI/FOMC events,
  2019-05-10 through 2026-10-14

The 2018 and 2026 pieces are partial calendar years.

---

## Project layout

```text
SkyQ_NewLondon/
  data/nq_1m.parquet              # NQ continuous 1-minute data
  data/economic_calendar.csv      # major NFP/CPI/FOMC dates
  skyq_newlondon/
    config.py                     # instrument, session, cost, filter settings
    data.py                       # loading and 5-minute resampling
    strategy.py                   # range, first break, stop/target, simulation
    mae.py                        # truncated MAE, prior-month stops, best book
    backtest.py                   # one-trade-per-day replay and range cap
    report.py                     # metrics, CSV/JSON/text outputs
  scripts/run_backtest.py         # default best; --base for control
  scripts/build_version_comparison.py
  scripts/analyze_patterns.py
  scripts/run_mae_stop.py
  tests/test_strategy.py          # 12 deterministic checks
  tests/test_mae.py               # 6 deterministic checks
  RESEARCH.md                     # pattern/news/MAE findings
  FAILED_VERSIONS.md              # side-by-side failed-version record
  logs/
    nq_london_best_mae_q50_range090_report.txt
    nq_london_best_mae_q50_range090_trades.csv
    nq_london_best_mae_q50_range090_summary.json
    nq_london_best_mae_q50_range090_yearly.csv
    nq_london_best_mae_q50_range090_side.csv
    nq_london_best_mae_q50_range090_exits.csv
    nq_london_best_mae_q50_range090_monthly.csv
    nq_london_best_mae_q50_range090_equity.csv
    nq_london_base_8y_*           # base control outputs
    nq_london_8y_mae_stop_*       # uncapped MAE variants
    nq_london_version_comparison.csv
    nq_london_version_comparison.md
  requirements.txt
  run_backtest.ps1
```

The best ledger and the version-comparison outputs are the source of truth for
the default numbers. `RESEARCH.md` is the source of truth for the research
process.

---

## Limitations

- **Backtest only.** No live execution, broker, order router, or risk engine.
- **In-sample selection.** The 0.90% cap and q50 stop were selected on this
  eight-year sample. A rolling walk-forward test is still required.
- **Recent regime risk.** 2026 is negative; 2025 supplies most of the profit.
- **1-minute OHLC cannot reveal intrabar order.** Stop-first is conservative,
  but actual fills can differ.
- **No order-book, queue, partial-fill, or liquidity model.**
- **No roll modeling.** NQ continuous data ignores quarterly roll gaps and
  contract-specific liquidity.
- **Fixed one-contract sizing.** No compounding, margin, financing, taxes, or
  account-level risk limits. The largest planned stop in the default was
  $4,484; a $35k drawdown is not a small-account risk profile.
- **Cost assumptions are models.** $0.62/side and one tick are not measured
  fills.
- **MAE adaptation.** The MAE is truncated at the base 2R target, not at a
  50%-of-range target. A 10-observation prior-month minimum can make the q50
  unstable in quiet months.
- **No claim of profitability.** Past backtest results do not guarantee future
  results. This is research, not financial advice.
