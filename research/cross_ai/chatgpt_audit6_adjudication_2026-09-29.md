# ChatGPT audit #6 — adjudication by Cowork (2026-09-29, 23:30Z)

The audit was run on `main` @ `145a1fee0`, from brief v5. Cowork checked each finding against the code at that
commit before accepting it. The result is that almost everything the auditor raised holds. The claims that fail
are Cowork's own:
- the runbook's reader filter;
- the sidecar targets;
- "anchored means the book's probability";
- the game-line cutoff;
- "London is fair";
- the wording about which team is charged the timeout.

**Decision.** Thursday's TNF run is a **pilot** (`--pilot`), a smoke test of the live path only. The primary forward
count starts at the first kick window after FWD2 is verified. The target is London, 12:45Z Sun 10-04; if FWD2 is not
verified by then, the count starts at week 5. v1's physics stay frozen (Q8); no v2.

## Findings (A1-A7), checked by Cowork at 145a1fee0

| # | Finding | Cowork check | Verdict |
|---|---|---|---|
| A1 | Scoring does not implement D210 | `score()` filters only revision and pilot. `score_report` P1 pools every graded two-way row, including other readers, `no_view` rows and game lines. The anchor sidecar is never read. There is no bootstrap. | **HOLDS** |
| A2 | Sheet, sim and freeze read inputs separately; game lines are not capped at now | `newest_inputs` takes `snap_*.parquet[-1:]`, the newest file on disk, whatever the `now`. freeze() rebuilds the sheet itself. run_week gets no --as-of or window. The pilot's 48 game-line rows (outside the sim-only score) were sourced 09-29 inside a 09-27 freeze. | **HOLDS.** Live runs are only mildly exposed (the tape files are all earlier than now). The single-bundle design is still required. |
| A3 | The freeze does not identify the full system; a calibration mismatch does not halt | `test_freeze_v1` has 4 tests and none compares `usage_fingerprint`. run_week.py:502-507: a stamp mismatch only sets `sim_pricing_enabled=False`, and `cal_p` is still written. | **HOLDS** |
| A4 | A second "first opinion" is possible | `prior_revisions(d, reader_model=…)` looks up the raw string, and freeze() stores `.strip()`. A different reader string, or a different week directory, also resets the count. | **HOLDS** |
| A5 | Matching has no event or player identity; the props loader mixes books | `fill_sheet` keys on (player_name, market, line). run_week.py:339-: the loader reads every file of every book and prefers tag over time ("close > mid > open"). | **HOLDS.** Frozen prices come from the logger (Hard Rock only), so P2 prices are not contaminated. |
| A6 | The sidecar targets have the wrong sign; it picks the wrong iteration | err = target − mean, but the sidecar used mean − err (Cowork passed this in D218 and D222). Separately, the solver returns at the first converged iteration while the sidecar picks the minimum-error one. The sidecar is written after the freeze and overwritten weekly. | **HOLDS** |
| A7 | Settlement | `_first_side_won`: a resolved player with no stats row gets 0, so an inactive player's Under is scored a WIN (Hard Rock voids these). There is no completed-game check, and games are matched by team pair. | **HOLDS.** It also affects the **AI blind-log grades already reported** (N59/N60, weeks 2-3). They need a re-grade under the new rule once it exists. |

## Q-verdicts, adjudicated

- **Q1 (identity).** Accepted. The two-record design is adopted: an experiment manifest plus a per-run bundle.
- **Q2 (point in time).** Accepted:
  - team ratings stop at week 2 for a week-4 run;
  - kickers have no 2026 rows;
  - depth and injury inputs are not filtered by acquisition time.

  FWD2 adds a pre-run refresh, and a freshness check that halts the run.
- **Q3 (metric).** Accepted. The primary statistic is Δ = mean[(p−y)² − (q−y)²] on the eligible cohort, with a
  whole-game bootstrap, 50,000 resamples and a fixed seed. 500 legs is descriptive and 1,500 is the one confirmatory
  checkpoint. P2 is secondary. **Cowork's D209 statement that game-line probabilities equal the book's "by
  construction" is withdrawn: it is false.**
- **Q4.** Accepted. One canonical reader and one experiment; duplicate primary contracts are refused across weeks.
- **Q5.** Accepted. The harness tests do not exercise `main()` end to end.
- **Q6.** Accepted. D209's "D206+D207 moved points by ~0" was a combined A/B; the components were not separated.
  `shift(-1)` measures the next row, not the next snap. The timeout side forces team 0 only when both teams have
  timeouts left.
- **Q7.** Window coverage holds: 16 games, no overlaps. The "London is fair" claim is withdrawn: a 22 h 45 m quote is
  not an executable price at freeze. A Sunday pre-London pull and a quote-age limit are required. The runbook's day
  labels are also wrong: SNF is Mon 10-05 00:20Z and MNF is Tue 10-06 00:15Z.
- **Q8.** Accepted. Keep v1's physics fixed and repair the experiment first.

## What the auditor recomputed and found to hold
- K1 aggregates.
- The pilot population (174 opinions: 139 receptions / 35 rush attempts).
- The pilot Brier (0.2673 / 0.2517) and its interval (−0.0021, +0.0339).
- The pilot units: −10.78 on all sides and +3.73 on the P2 subset.
- Week-2 anchoring at 15/15.
- "10 reds, not 11", and the red values.
- The 16 tests.

It also read the 6E K4 file, which Cowork had not: the sim is worse than the book in all 8 families.

### D223 — ChatGPT audit #6 adjudicated: the forward experiment is not yet valid; Thursday is a pilot; primary count starts after FWD2 (2026-09-29)

Every one of A1-A7 is confirmed against the code at 145a1fee0:
- scoring pools readers, no_view rows and game lines, and has no anchor join or bootstrap;
- the sheet, sim and freeze read inputs separately, and game lines are not capped at the freeze time;
- the freeze does not compare the usage fingerprint, and a calibration-stamp mismatch does not halt;
- the reader string is not canonicalized before the revision lookup;
- matching has no event or player id;
- the sidecar targets have the wrong sign and it picks the wrong iteration;
- an inactive player's Under is scored a win.

Cowork's own claims withdrawn:
- "anchored ⇒ the book's probability" (D209);
- the London fairness claim (D222);
- the sidecar and reader-filter acceptance (D218, D222).

Decisions:
- The week-4 TNF run is `--pilot`.
- The primary count of reader nfl_sim_v1_156cd057 starts at the first window after FWD2 is verified.
- v1's physics stay frozen.
- The primary statistic is the Brier difference on the eligible cohort, with a 50,000-resample whole-game bootstrap;
  1,500 legs is confirmatory and 500 descriptive.
- Earlier AI blind-log grades are re-graded under the FWD2 settlement rule.
