# CC-4 Report

## Close defect cause (CC-D9a)

The Odds API updates each event's `commence_time` as game time approaches. NHL listed starts
are typically moved forward by ~8–25 min (reflecting puck drop timing). `build_tables.py` used
`events = inplay[...].drop_duplicates("event_id")` which takes the FIRST `commence_time` seen
(the earliest), but the pre-tip filter `snap < ct` uses each row's OWN `ct` (the later, updated
value). Result: a snapshot at 03:20 with its own `ct=03:25` passes the per-row filter, but the
games table records `ct=03:00` (from the first snapshot), so `close_age_min = 03:00 - 03:20 = -20`.

Evidence: 20 sampled negative-age NHL games all showed `tape_ct_min == games_ct` and
`tape_ct_max > games_ct` by 8–35 min, with the close snapshot falling between the two values.

NBA shows the same pattern: 137/2546 (5.4%) negative close ages, from the same cause in
`lines_hourly`.

## Rule A distributions

After implementing close rule A (`listed_start = MAX ct`; close = last snapshot with
`snap <= listed_start`; `close_age_min = listed_start - close_snap`):

| Sport | n_negative (before) | n_negative (after) | median (min) | p90 (min) | share > 60 min |
|---|---|---|---|---|---|
| NHL | 1,132 | 0 | 4.3 | 4.4 | 0.5% |
| NBA | 137 | 0 | 9.4 | 19.4 | 3.3% |

**Key finding:** Rule A close selection produces **identical close prices** to the legacy method
for every NHL and NBA game. The defect was purely in the `close_age_min` computation (wrong ct
for the subtraction), not in the actual close selection. `snap < per_row_ct` and `snap <= max_ct`
select the same last snapshot for every event.

## v2 vs v3 side-by-side: NHL Tier 1

| Cell | n(v2) | r(v2) | p(v2) | n(v3) | r(v3) | p(v3) | Verdict change |
|---|---|---|---|---|---|---|---|
| NH1 | 246 | −0.018 | 0.712 | 246 | −0.018 | 0.712 | No |
| NH2 | 218 | +0.047 | 0.085 | 218 | +0.047 | 0.085 | No |
| NH3 | 76 | −0.064 | 0.870 | 76 | −0.064 | 0.870 | No |
| NH4 | 149 | +0.042 | 0.151 | 149 | +0.042 | 0.151 | No |
| NH5 | 13 | +0.120 | 0.188 | 13 | +0.120 | 0.188 | No |
| NH6 | 132 | +0.032 | 0.223 | 132 | +0.032 | 0.223 | No |
| NH7 | 56 | +0.131 | 0.024 | 56 | +0.131 | 0.024 | No |

All 7 NHL Tier 1 cells: identical n, r, p. **0 verdict changes.**

## v2 vs v3 side-by-side: BH survivors

| Cell | n(v2) | r(v2) | p(v2) | n(v3) | r(v3) | p(v3) | BH(v3) |
|---|---|---|---|---|---|---|---|
| f1_divergence_flag_yes_under | 605 | +0.069 | 0.0003 | 605 | +0.069 | 0.0003 | YES |
| f1_divergence_band_small_under | 589 | +0.065 | 0.0007 | 589 | +0.065 | 0.0007 | YES |
| f1_divergence_band_medium_under | 12 | +0.360 | 0.0048 | 12 | +0.360 | 0.0048 | YES |
| total_move_band_up_away_ml | 244 | +0.084 | 0.0040 | 244 | +0.084 | 0.0040 | YES |

All 4 v2 BH survivors survive under rule A with identical values. 0 new, 0 removed.

## NH8 rule-A row with CHECK 5

NH8 as registered (close rule A, 9 books, same snapshot, blu ≤ 10 min, |Δ| ≥ 0.02, UNDER):

| Metric | Value |
|---|---|
| n | 567 |
| r | +0.068 |
| SE | 0.021 |
| p (one-sided) | 0.00057 |
| Excess over pop under base (+0.022) | +0.046 |
| Season 2022 | n=247, r=+0.090 |
| Season 2023 | n=320, r=+0.051 |
| ROI at best soft under | +10.7% (SE 4.2%, n=559) |
| ROI at Pinnacle | +10.4% (n=567) |
| share_largest_sm | 0.176 |

CHECK 5 breakdowns:
- **Season:** same sign both seasons (+0.090, +0.051)
- **Month:** 6/7 positive; January negative (−0.018)
- **Fav/dog:** driving_on_fav +0.078 (n=111), driving_on_dog +0.066 (n=456)
- **Total band:** 5.5 +0.077 (n=69), 6.0 −0.005 (n=179), 6.5+ +0.107 (n=319)
- **Depth:** all games in one tercile (n_fresh_books all similar)

## Q table: flagged vs unflagged, by season

| Q | Measure | Flagged | Unflagged | Diff | p (one-sided) | Result |
|---|---|---|---|---|---|---|
| Q1 (price footprint) | mean(soft−pin over prob) | +0.0016 | +0.0024 | −0.0008 | 0.773 | **FAIL** |
| Q2 (side footprint) | share driving_on_fav | 19.6% | — | — | 1.000 | **FAIL** |
| Q3 (pace) | att60 % diff vs prior-10 | +0.15% | −0.27% | +0.42% | 0.735 | **FAIL** |
| Q4 (luck, diagnostic) | sh% diff vs prior-30 | −0.0019 | +0.0005 | −0.0024 | 0.063 | **SOLE** |

By season (Q3):
- 2022: flagged +0.93%, unflagged −0.33%
- 2023: flagged −0.45%, unflagged −0.20%

**Filter verdict: FAIL.** None of Q1–Q3 holds. Q4 (shooting %) is the sole explanation:
flagged games have lower realised shooting relative to the prior-30-day league average, which
is consistent with finishing luck driving the under excess, not a priced mechanism.

Q2 is particularly informative: the driving book is higher on the favourite only 19.6% of the
time — the divergence is overwhelmingly on the underdog side, directly contradicting the M1
(action-balancing) hypothesis.

**NH8 is DROPPED.**

## Dry-run output and identity test

```
confirm_nh8.py --season 2023:
  n = 320
  r = +0.0510
  SE = 0.0278
  p (one-sided) = 0.033915
  90% lower bound = +0.0051
  Population under base = +0.0284 (n=1237)
  Excess over base = +0.0226
  ROI at best soft under = +0.083 (SE=0.055, n_priced=320)
  ROI at Pinnacle = +0.072 (n=320)
  OVERALL: PASS
```

Identity test (CHECK 3): n=320, r=+0.0510, SE=0.0278 — matches Item 1a's 2023-24 row
to 4 decimals. **PASS.**

Bug found and fixed: Montréal Canadiens accent encoding (é vs e) caused 82 unmatched games
in the initial confirm build. Now uses `unicodedata.normalize` matching `build_tables.py`.

## What the numbers mean (separate from what the commands returned)

1. The close defect was cosmetic: it affected `close_age_min` reporting but not actual close
   prices. All v2 screen results are valid.

2. NH8's screen residual (+0.068, excess +0.046 over base) is real in the data — both seasons
   positive, survives BH, high ROI. But the mechanism filter is designed to distinguish
   structure from luck, and NH8 fails it. The under excess in flagged games is best explained
   by below-average shooting (Q4), not by action balancing (M1, Q1+Q2 both FAIL) or pace
   suppression (M2, Q3 FAIL).

3. The CONFIRM script reproduces the DEV row exactly and is ready for Cowork verification.
   The one-shot 2024-25 look (CC-5) would be mechanically possible but is moot since NH8 is
   DROPPED. The script remains useful as infrastructure for future cells.

## NOT DONE

- CC-5 (the 2024-25 look with `--season 2024`) — not run, by design (requires Cowork
  verification first, and NH8 is DROPPED regardless)
- Merge to main — not done, per work order

## UNVERIFIED

- Whether the `close_age_min` cosmetic defect affected any downstream reporting or decisions
  in prior CC sessions. The actual close prices were unaffected, so screen results are valid,
  but any analysis that relied on `close_age_min` values (e.g., the "44% of closes were 5–30
  min after listed start" finding in CC-3) was reporting on a defective metric.
- The CONFIRM script's SBRO matching on seasons other than 2023 — only season=2023 has been
  tested.
