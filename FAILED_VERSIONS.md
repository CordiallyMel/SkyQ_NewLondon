# SkyQ_NewLondon — failed and rejected versions

This file exists so the weaker books are not hidden behind the default's
headline. Every row is a real run through the same NQ engine and cost model.
**All results are in-sample backtests.** The default is a research candidate,
not a live track record.

- Window: 2018-10-23 through 2026-10-23
- Instrument: NQ, one contract, $20/point
- Commission: $0.62/side
- Slippage: one tick on entry, stop exits, and time exits
- Same-bar rule: stop is assumed first
- Sharpe / Sortino: daily, annualized

## Full comparison

| Variant | Status | Trades | Win % | Net P&L | PF | Max DD | Sharpe | Sortino | Avg stop | Target / stop / time |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **MAE q50 + 0.90% range cap** | **DEFAULT** | **1,343** | **38.12%** | **+$97,430.51** | **1.130** | **$35,184.30** | **0.59** | **0.67** | **50.38 pts** | **403 / 773 / 167** |
| Range cap only | Superseded | 1,498 | 37.85% | +$64,302.48 | 1.108 | $33,542.60 | 0.52 | 0.61 | 31.62 pts | 534 / 912 / 52 |
| MAE q50, uncapped | Candidate, not default | 1,928 | 38.28% | +$61,083.59 | 1.044 | $51,675.40 | 0.25 | 0.32 | 64.66 pts | 536 / 1,106 / 286 |
| MAE q75, uncapped | Rejected | 1,928 | 44.81% | +$136,907.96 | 1.070 | $78,574.44 | 0.39 | 0.44 | 134.92 pts | 260 / 706 / 962 |
| MAE q90, uncapped | Rejected | 1,928 | 48.76% | +$167,195.23 | 1.077 | $90,823.04 | 0.41 | 0.44 | 221.52 pts | 94 / 370 / 1,464 |
| MAE q95, uncapped | Rejected | 1,928 | 49.74% | +$168,568.32 | 1.076 | $90,875.13 | 0.40 | 0.41 | 281.38 pts | 46 / 255 / 1,627 |
| MAE prior-month mean, uncapped | Rejected | 1,928 | 42.12% | +$68,479.46 | 1.039 | $78,848.14 | 0.22 | 0.26 | 97.32 pts | 374 / 920 / 634 |
| **Base book** | **Control / rejected** | **1,955** | **36.37%** | **−$19,774.20** | **0.979** | **$57,933.08** | **−0.12** | **−0.16** | **36.49 pts** | **669 / 1,221 / 65** |

## What failed, and why

### Base book — failed

The original rules lost **$19,774.20** over eight years, with a 0.979 profit
factor, a $57,933 drawdown, and only 47 of 97 positive months. The zero-cost
result was also slightly negative. It is retained behind `--base` for
reproducibility and as a control, not as a product.

### Range cap only — improved, but superseded

The 0.90% London-range cap alone made **+$64,302.48**, PF 1.108, with a
$33,542.60 drawdown. It was the strongest single filter in the pattern study.
The default adds the q50 stop, which raises net, PF, Sharpe, and Sortino while
keeping drawdown close to the cap-only level.

### MAE q50 uncapped — candidate, not default

The uncapped q50 stop made **+$61,083.59**, but had a **$51,675.40** drawdown
and only a 0.25 Sharpe. Applying the range cap first produces the default's
$97,430.51 at a $35,184.30 drawdown. The uncapped version is retained as a
stop-study result.

### MAE q75/q90/q95 — rejected as defaults

The high-percentile variants produce larger nominal P&L, but they do so by
widening the stop to **135–281 NQ points**:

- q75: 962 of 1,928 trades (49.9%) are time exits; drawdown $78,574.
- q90: 1,464 of 1,928 (75.9%) are time exits; drawdown $90,823.
- q95: 1,627 of 1,928 (84.4%) are time exits; drawdown $90,875.

At q90/q95 the 2R target is rarely reached. That is a different strategy — a
wide-stop hold-to-close book — not a better version of a tight 2R breakout.
The nominal P&L is also concentrated in 2025–2026. These versions are rejected
as defaults.

### Prior-month mean — rejected

The literal mean stop made **+$68,479.46**, but with a **$78,848.14** drawdown
and a heavy dependence on 2025 (+$90,305). It is wider than q50 and does not
improve the risk profile.

## Default's honest caveats

- 2026 is **negative** (−$3,507.19), and the max drawdown occurs in that
  partial year.
- 2025 contributes **+$55,464.66** of the +$97,430.51 total.
- 2022 and 2024 are also negative.
- Sharpe **0.59** and Sortino **0.67** are not strong enough to call this a
  validated institutional edge.
- The largest planned stop was **$4,484.18**; this is not a small-account
  strategy at one NQ contract.
- The 0.90% threshold and q50 rule were selected on this sample. A rolling
  walk-forward test, paper trading, and live fill audit are still required.

## Reproduce

```powershell
..\SkyQ_Scan\.venv\Scripts\python.exe scripts/run_backtest.py
..\SkyQ_Scan\.venv\Scripts\python.exe scripts/run_backtest.py --base
..\SkyQ_Scan\.venv\Scripts\python.exe scripts/build_version_comparison.py
```

Machine-readable table: `logs/nq_london_version_comparison.csv`.
