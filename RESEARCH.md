# SkyQ_NewLondon — Pattern, News, and MAE Stop Research

> **2026-11-16 update:** the researched default is now **prior-month MAE q50 +
> a 0.90% London-range cap**, with the cap applied before the MAE statistics are
> built. The base book remains reproducible with `--base`. The default made
> **+$97,430.51** over 1,343 trades, PF 1.130, max drawdown $35,184.30, Sharpe
> 0.59, Sortino 0.67. See `README.md` and `FAILED_VERSIONS.md`. This is still an
> in-sample research result, not a live track record.

This is a research layer on top of the unchanged base book. None of the filters
below were added to the base strategy. Everything here is in-sample unless
explicitly described as prior-month walk-forward.

## Base ledger

- 1,955 trades
- 2018-10-23 through 2026-10-23
- Net: **−$19,774.20**
- Profit factor: **0.979**
- Max drawdown: **$57,933.08**

## Pattern method

- Group net P&L, win rate, profit factor, expectancy, and max drawdown.
- Permutation test of each group's mean net versus the rest (2,000 shuffles).
- Bootstrap 95% confidence interval for the group mean.
- First half = 2018-10-23 to 2022-12-31; second half = 2023-01-01 to 2026-10-23.
- Bonferroni-adjusted p-values within each multi-category table.
- A slice was only called a candidate if it had at least 50 trades, a
  Bonferroni p below 0.05, and the same sign in both halves.

The point of the screen is to avoid presenting a random 8-year slice as an
edge. The base trade count is large, but many calendar slices have only 80–300
observations.

---

## Day of week

| Day | Trades | Net P&L | PF | p (Bonferroni) | Halves same sign |
|---|---:|---:|---:|---:|---|
| Monday | 381 | −$21,577 | 0.887 | 1.000 | yes |
| Tuesday | 402 | −$16,343 | 0.916 | 1.000 | yes |
| Wednesday | 393 | +$23,398 | 1.137 | 1.000 | yes |
| Thursday | 403 | +$17,045 | 1.092 | 1.000 | no |
| Friday | 376 | −$22,296 | 0.889 | 1.000 | yes |

**Verdict: no usable day-of-week filter.** Friday and Monday are the worst,
but neither survives multiple-testing correction, and the confidence intervals
include zero.

---

## Month of year

| Month | Trades | Net P&L | PF | p (Bonferroni) | Halves same sign |
|---|---:|---:|---:|---:|---|
| January | 164 | −$3,673 | 0.955 | 1.000 | no |
| February | 153 | −$8,420 | 0.888 | 1.000 | no |
| March | 160 | −$34,468 | 0.674 | 0.570 | yes |
| **April** | **156** | **+$50,647** | **1.710** | **0.012** | **yes** |
| May | 163 | +$7,558 | 1.097 | 1.000 | no |
| June | 163 | −$25,642 | 0.696 | 1.000 | yes |
| July | 170 | +$11,779 | 1.162 | 1.000 | yes |
| August | 168 | −$1,713 | 0.978 | 1.000 | no |
| September | 164 | −$5,188 | 0.933 | 1.000 | yes |
| October | 169 | −$10 | 1.000 | 1.000 | no |
| November | 162 | +$6,349 | 1.108 | 1.000 | no |
| December | 163 | −$16,992 | 0.772 | 1.000 | yes |

**April is the one month that survives the month-level screen**, but it is not
a clean independent rule:

- April 2025 alone made **+$27,070**; April excluding 2025 still made **+$23,576**.
- Seven of eight Aprils were positive; 2019 was the exception.
- The gain is concentrated in **April wide ranges**: April wide +$41,568,
  April narrow +$9,078.
- Wide ranges are the worst bucket overall, so the April/wide interaction is a
  hypothesis about a specific volatility regime, not a general edge.

**Verdict: April is worth an out-of-sample check, not a live filter.**

---

## Entry time bucket

| Entry time | Trades | Net P&L | PF | p (Bonferroni) |
|---|---:|---:|---:|---:|
| 09:30–09:44 | 1,607 | −$33,258 | 0.954 | 1.000 |
| **09:45–09:59** | **170** | **+$38,304** | **1.364** | **0.060** |
| 10:00–10:14 | 87 | −$23,383 | 0.639 | 0.378 |
| 10:15–10:29 | 37 | −$6,761 | 0.719 | 1.000 |
| 10:30–10:44 | 28 | +$8,880 | 1.742 | 1.000 |
| 10:45–10:59 | 26 | −$3,557 | 0.739 | 1.000 |

The 09:45–09:59 bucket is the best slice, but it misses the Bonferroni
threshold and is only 170 trades. The 10:00–10:14 bucket is negative but not
significant. **Verdict: no time-window filter yet.** The broad statement
"after 10:00 is weak" is too strong for this sample.

---

## Day of month / OpEx / month-end

| Pattern | Trades | Net P&L | PF | p |
|---|---:|---:|---:|---:|
| Day 11–15 | 318 | −$53,329 | 0.697 | 0.144 (Bonferroni) |
| Day 21–25 | 322 | +$33,531 | 1.228 | 0.522 (Bonferroni) |
| OpEx Friday | 90 | −$14,152 | 0.734 | 0.268 (raw) |
| First Friday | 84 | −$4,234 | 0.903 | 0.766 (raw) |
| **Month-end (last 3 business days)** | **270** | **+$46,600** | **1.391** | **0.0175 (raw)** |
| Quarter-end | 91 | +$4,122 | 1.092 | 0.700 (raw) |

Month-end is the second interesting calendar slice, but:

- Its raw p is 0.0175; a four-test Bonferroni correction is about 0.07, so it
  does not pass the screen.
- It is positive in six of nine years, but 2018, 2019, and 2023 were negative.
- It is not additive with the range filter: month-end + narrow is +$33,985,
  while other days + narrow is +$34,553. The narrow/wide split carries the
  information, not month-end itself.

**Verdict: month-end is a secondary hypothesis, not a reason to alter the book.**

---

## Major U.S. news days

The usable event schedule covers **2019-05-10 through 2026-10-14**:
91 NFP dates, 94 CPI dates, and 65 FOMC dates. Times used are the conventional
08:30 ET for NFP/CPI and 14:00 ET for FOMC. The event-covered sample has 1,813
trades; 217 occurred on a major event day.

| Comparison | Event day | No event | p |
|---|---:|---:|---:|
| Any NFP/CPI/FOMC | 217 trades, −$3,909 | 1,596 trades, −$3,709 | 0.874 |
| NFP only | 80 trades, +$746 | 1,733 trades, −$8,364 | 0.929 |
| CPI only | 78 trades, −$2,662 | 1,735 trades, −$4,956 | 0.850 |
| FOMC only | 62 trades, −$752 | 1,751 trades, −$6,866 | 0.969 |
| Pre-open NFP/CPI | 158 trades, −$1,916 | 1,655 trades, −$5,702 | 0.939 |

**Verdict: no measurable major-news edge or penalty.** The event-day and
no-event groups are effectively the same. There is no basis here for a
news-avoidance or news-only filter.

Coverage limits:

- Only NFP, CPI, and FOMC are available with reliable dates across the full
  period.
- The raw Forex Factory cache had unreliable pre-2019 timestamps and is not
  used for the event study.
- This is a major-event study, not a full economic-calendar event-window study.

---

## The strongest pattern: wide London ranges

| Range bucket | Trades | Net P&L | PF | p (Bonferroni) | Halves |
|---|---:|---:|---:|---:|---|
| ≤ 0.397% of price | 489 | +$29,754 | 1.223 | 0.658 | positive / positive |
| 0.397–0.579% | 489 | +$29,529 | 1.146 | 0.686 | positive / positive |
| 0.579–0.869% | 488 | +$9,255 | 1.038 | 1.000 | positive / negative |
| **> 0.869%** | **489** | **−$88,311** | **0.756** | **0.002** | **negative / negative** |

The top quartile is the only broad pattern that is both economically large and
statistically persistent in both halves. It loses in seven of nine years; 2024
and 2025 are the exceptions.

A simple **range ≤ 0.90% of entry price** filter gives:

- 1,498 trades
- Net **+$64,302**
- PF **1.108**
- Max DD **$33,543**
- First half **+$53,076**, second half **+$11,227**

The second half is still weak, so this remains an in-sample candidate. It is
the best next walk-forward test, not a finished rule.

---

## Prior-month truncated-MAE stop experiment

### Method

This adapts the Dokakuri-style idea to this book:

1. Measure each entry's adverse excursion from entry until the **base 2R target**
   is touched, then truncate. If the target is never touched, measure through
   the 16:00 ET exit. This is the walk-away MAE definition: heat after a target
   would already have closed the trade is excluded.
2. Express MAE as a **percentage of the London range**.
3. For each current calendar month, use only the prior month's MAE distribution.
4. Set the stop at the selected prior-month MAE percentile (median, 75th, 90th,
   or 95th) or the prior-month arithmetic mean, times the current London range,
   plus the one-tick buffer.
5. Keep the target at 2R from the new stop.
6. Skip months with fewer than 10 prior-month observations. 27 of 1,955 entries
   were skipped, leaving 1,928 for the apples-to-apples comparison.

No current-month data is used in that month's stop. This is a walk-forward
statistic, not a full-sample fit.

### Results

The base-subset row is the same 1,928 entry dates as every MAE row.

| Variant | Trades | Win rate | Net P&L | PF | Max DD | Avg stop | Target / stop / time exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| Base subset | 1,928 | 36.31% | −$15,286 | 0.984 | $57,933 | 36.70 pts | 659 / 1,206 / 63 |
| MAE q50 | 1,928 | 38.28% | +$61,084 | 1.044 | $51,675 | 64.66 pts | 536 / 1,106 / 286 |
| MAE q75 | 1,928 | 44.81% | +$136,908 | 1.070 | $78,574 | 134.92 pts | 260 / 706 / 962 |
| MAE q90 | 1,928 | 48.76% | +$167,195 | 1.077 | $90,823 | 221.52 pts | 94 / 370 / 1,464 |
| MAE q95 | 1,928 | 49.74% | +$168,568 | 1.076 | $90,875 | 281.38 pts | 46 / 255 / 1,627 |
| MAE mean | 1,928 | 42.12% | +$68,479 | 1.039 | $78,848 | 97.32 pts | 374 / 920 / 634 |

The nominal P&L improvement is real in the ledger, but it comes with a major
change in the trade profile. At q90/q95, the stop is so wide that the 2R target
is rarely reached; most trades become **time exits**. The strategy is no longer
a tight 2R breakout; it is a wide-stop, hold-to-close book.

### Yearly dependence

| Year | Base subset | q50 | q75 | q90 | q95 | mean |
|---:|---:|---:|---:|---:|---:|---:|
| 2018* | −$6,827 | −$11,578 | −$4,143 | −$677 | −$860 | −$12,861 |
| 2019 | +$12,877 | +$3,081 | +$4,755 | +$9,064 | +$9,525 | +$1,230 |
| 2020 | −$20,679 | −$17,095 | −$17,015 | −$11,462 | −$12,342 | −$22,068 |
| 2021 | +$16,670 | +$146 | +$2,070 | +$8,438 | +$13,115 | +$3,083 |
| 2022 | −$5,754 | +$8,473 | +$21,104 | +$7,396 | +$37,959 | +$23,797 |
| 2023 | −$13,529 | +$2,103 | −$2,312 | +$11,948 | +$6,869 | −$2,249 |
| 2024 | +$5,334 | +$27,524 | +$16,666 | +$15,736 | +$29,468 | +$2,463 |
| 2025 | +$27,547 | +$56,192 | +$74,587 | +$35,181 | +$13,999 | +$90,305 |
| 2026* | −$30,926 | −$7,762 | +$41,197 | +$91,572 | +$70,837 | −$15,221 |

\*Partial year. 2018 starts 2018-10-23; 2026 ends 2026-10-23.

The q90 headline is heavily dependent on 2026: +$91,572 of its +$167,195 total.
The q50 variant is more balanced by year but has a **negative first half**
(−$16,973) and a **positive second half** (+$78,056). The literal mean variant
is worse on drawdown ($78,848) and is even more 2025-dependent: +$90,305 in
2025, −$15,221 in 2026, and −$6,818 in the first half. It is not a stable
standalone replacement.

### MAE distribution

Across all 1,955 entries, truncated MAE as a percentage of the London range was:

- Median: 56.8%
- 75th percentile: 129.9%
- 90th percentile: 230.0%
- 95th percentile: 298.1%
- Mean: 91.6%
- Target touched before time exit: 61.6%

A stop at the "average" heat would therefore be far wider than the base
prior-bar stop. That is exactly why the q75/q90 results change the character of
the book.

### Verdict

- **q50 was the only version worth promoting.** It has the smallest drawdown
  increase ($51.7k vs $57.9k), the most reasonable stop (64.7 points), and the
  least reliance on time exits. Combined with the 0.90% cap, it became the
  default at +$97,430.51 and a $35,184.30 drawdown. Its first half was negative
  without the cap; the cap changes the eligible-entry set.
- **q75, q90, q95, and the mean are not clean improvements.** They buy nominal
  P&L with 97–281-point stops, much larger drawdowns, and a 33–84% time-exit
  mix. q90/q95 are effectively a different strategy.
- If this line is pursued, cap the MAE stop (for example at 1.5–2.0× the London
  range), and test the capped q50 rule on a separate walk-forward period.
- Do not replace the base prior-bar stop with the uncapped q90/q95 rule on the
  strength of this sample.

---

## Bottom line

1. **No day-of-week filter.**
2. **No major-news filter.** NFP, CPI, and FOMC days look like ordinary days.
3. **The wide-range filter remains the strongest lead.** It is the only broad
   pattern with both economic size and two-half persistence.
4. **April and month-end are interesting but secondary.** April survives the
   month-level screen; month-end does not survive a four-test correction and is
   not additive with the range filter.
5. **The 09:45–09:59 time bucket is borderline, not established.**
6. **Prior-month MAE stops are promising but fragile.** q50 is now the default
   only in combination with the 0.90% cap; it still needs a rolling
   out-of-sample test. q90/q95 do not deserve a promotion.

## Files

- `logs/nq_london_8y_patterns.txt` — full pattern report
- `logs/nq_london_8y_patterns_*.csv` — slice tables
- `logs/nq_london_8y_mae_stop_report.txt` — MAE summary
- `logs/nq_london_8y_mae_stop_summary.csv` — variant comparison
- `logs/nq_london_8y_mae_stop_q*_trades.csv` and `..._mean_trades.csv` — variant ledgers
- `logs/nq_london_8y_mae_stop_observations.csv` — truncated MAE observations
- `data/economic_calendar.csv` — major-event schedule used here

## Limitations

- All pattern slices and filter simulations are in-sample.
- Multiple testing remains a risk even with Bonferroni adjustment.
- The event study covers only major NFP/CPI/FOMC events, not every release.
- The MAE stop uses the base 2R target as its truncation point, not a 50%-of-
  range target. It is an adaptation of the Dokakuri idea to this book.
- The MAE stop relies on prior-month heat; a regime change can make it too wide
  or too tight. A 10-observation minimum can also make a 90th/95th percentile
  behave like the maximum of a small sample.
- The mean variant is included; its 97-point average stop and $78,848 drawdown
  do not improve on q50's risk profile.
- Costs, gap risk, and stop-first same-bar assumptions are unchanged.
