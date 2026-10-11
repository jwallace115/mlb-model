# Claude prediction ledger — started 2026-10-11

Why this exists (Jeff, 2026-10-11): "your wrong and you mess things up alot ... just as prone to be wrong and miss a
possible edge as you are to find one." The project defends hard against false positives and not at all against
false negatives. This ledger makes Claude's priors gradeable so Jeff can weight them, in both directions.

Rules. Every "I expect" / "my prior is" from Claude goes here as a number with a date, before the data is looked at.
Grades are written by whoever runs the test (Claude Code, Jeff, or the ChatGPT auditor), not by the Claude that
made the prediction, wherever that is practical. Two failure modes are tracked separately because they have
different fixes: (A) a prior about the WORLD that was wrong (bias — fix by re-weighting Claude's "no"); (B) a claim
about a FILE or a NUMBER in the repo that was wrong (sloppiness — fix: nothing from memory, only from a file read
in that session). A rejection Claude made that was later overturned by data is logged as a MISSED EDGE.

## Known misses on the record (back-entries, for calibration)

| date | claim | type | outcome |
|---|---|---|---|
| 2026-09-15 | Rejected the "5-zone yardage granularity" hypothesis for the scoring deficit | A | WRONG — it was the cause (5A-6, D24). MISSED EDGE class. |
| 2026-09-19 | `test_starting_qb_identity_2026` is structurally incapable of passing | A | WRONG — it was reporting stale depth data; went green on refresh. |
| 2026-09-19 | D70 pricer "wired" (verified from the diff) | B | WRONG — import with no call site (ChatGPT audit #3). |
| 2026-09-19 | D72 gate "suppresses" priced legs | B | WRONG — appended text, nothing consumed it. |
| 2026-10-10 | Cited K1 pts/team 22.49 (5A-7) as current in the GL-1 order | B | WRONG — current was 21.06 (phase6e); recalled, not read. |

## Open predictions

| id | date | prediction (number) | type | grade | graded by / when |
|---|---|---|---|---|---|
| P1 | 2026-10-10 | Baseline ridge: \|c_margin\| < 0.15, b ∈ 1±0.15 on 2021-23 | A | HELD (c −0.093, b 1.009) | Claude Code GL-1 |
| P2 | 2026-10-10 | Chosen hl_games ∈ [8, 40] | A | DID NOT HOLD (inf; surface flat, range 0.002) | Claude Code GL-1 |
| P3 | 2026-10-10 | Engine raw total within ±1.5 of market | A/B | DID NOT HOLD (−3.0). Partly B: I cited a stale K1. | Claude Code GL-1 |
| P4 | 2026-10-10 | corr(raw_m, mkt_m) ≥ 0.75 | A | HELD (0.822) | Claude Code GL-1 |
| P5 | 2026-10-10 | \|c_margin\| < 0.20 and c_total ∈ (−0.3, +0.1) | A | HALF — margin held (0.055); total did not (−0.334) | Claude Code GL-1 |
| P6 | 2026-10-10 | Engine P(\|m\|=3) < 14.5%, so no alt-line shape edge | A | HELD (12.3%) | Claude Code GL-1 |
| P7 | 2026-10-11 | HFA via J_FWD h0 = 0.172 lands mean margin within ±0.3 of 2.13 on first run | A | pending | GL-1b |
| P8 | 2026-10-11 | c_margin changes < 0.05 after HFA | A | pending | GL-1b |
| P9 | 2026-10-11 | p_home_win mean within ±0.02 of actual home-win rate after HFA | A | pending | GL-1b |
| LM-C1 | 2026-10-11 | Key-number crossing: 30% positive CLV at bar; 10% ATS | A | INTERIM (LM-1b): paid-price CLV negative in both sports (NFL −1.78pp valid N=15, NCAAF −2.64pp valid N=41). FAIL on CLV. Consistent with the 30% prior. | graded by: Claude Code LM-1b, 2026-10-11 |
| LM-C2 | 2026-10-11 | Hard Rock lag: 85% positive CLV; 50% ATS | A | INTERIM (LM-1b): paid-price CLV −1.91pp NFL (valid N=14), −2.33pp NCAAF (valid N=72). FAIL. The 85% prior was wrong about CLV at the paid price — the vig absorbs the directional edge. NFL ATS 62.6% (57-34) is suggestive but CLV is negative. **MISS for Cowork, type A.** | graded by: Claude Code LM-1b, 2026-10-11 |
| LM-C3 | 2026-10-11 | Early-week over-correction: 25% reverts measurably; 10% CLV; 5% ATS | A | INTERIM (LM-1b): paid-price CLV −2.56pp NFL (valid N=3), −2.12pp NCAAF (valid N=42). FAIL. NFL ATS 39.4% (13-20). Consistent with the 10% prior. | graded by: Claude Code LM-1b, 2026-10-11 |
| LM-C4 | 2026-10-11 | Reversal / fake steam: 15% CLV | A | pending (N=2 NFL, N=19 NCAAF — too rare; valid N even smaller) | season end |
| LM-C5 | 2026-10-11 | Hard Rock shade: 60% directional shade exists; 30% CLV; 15% ATS | A | INTERIM (LM-1b): directional shade exists (drift_pp +1.59 NFL, +1.01 NCAAF — HR's fair number does move toward Pinnacle close). But paid-price CLV is −0.75pp NFL (valid N=18), −1.28pp NCAAF (valid N=3). The shade does not overcome the vig. **LM-1's "underestimated" call is reversed** — on the honest metric, C5 FAIL/INSUFFICIENT METHOD, consistent with the 30% CLV prior. NFL ATS 17-12 (58.6%). | graded by: Claude Code LM-1b, 2026-10-11 |
| LM-C6 | 2026-10-11 | Weather totals over-reaction: 35% CLV | A | pending (0 fires; no spec found on disk) | season end / 2027 |
| LM-0 | 2026-10-11 | Of the six, at most ONE passes the full bar at season end (and it is C2 or C5) | A | INTERIM (LM-1b): on the paid-price scale, NO cell passes. C5 shows a real directional shade but negative CLV. C2 shows suggestive ATS but negative CLV. The "at most one" prior is on track; the "C2 or C5" pick was right about which cells are closest, but neither clears the bar. Final grade at season end. | graded by: Claude Code LM-1b, 2026-10-11 |

| P-LM1b-1 | 2026-10-11 | C5-registered paid-price CLV mean ≤ 0 in both sports | A | HELD (NFL −0.75, NCAAF −1.28) | Claude Code LM-1b, 2026-10-11 |
| P-LM1b-2 | 2026-10-11 | C5-bidir drift_pp stays positive (~+1pp) in both sports | A | HELD (NFL +1.55, NCAAF +1.93) | Claude Code LM-1b, 2026-10-11 |
| P-LM1b-3 | 2026-10-11 | C2 paid-price CLV negative in both sports | A | HELD (NFL −1.91, NCAAF −2.33) | Claude Code LM-1b, 2026-10-11 |

## Scoring

Probabilities are scored with the Brier score per prediction, averaged per type, at each look. A Brier near 0.25 on
type-A means Claude's priors are worth nothing; well below means they carry information; a one-sided pattern (most
misses are "said no, data said yes") is the false-negative bias Jeff suspects and is the thing to look for.
Type-B entries are counted, not scored: the target is zero.

## Standing "what did Claude dismiss" list

Appended at the end of each phase: ideas Claude argued against, in one line each, with whether the data on disk
could test them for free. Reviewed by Jeff or the auditor; any of them can be promoted to a registry cell by Jeff.

- 2026-10-11: "fade the public from bet-percentage sites" — dismissed for data quality (no trustworthy source).
  Testable for free: no.
- 2026-10-11: opening 2024 for the GL clean look now — dismissed as wasting the look on a null object. Testable for
  free: yes, but it consumes the look; Jeff can override.
- 2026-10-11: cells keyed on team / coach / primetime / revenge — dismissed as narrative with infinite cells.
  Testable for free: partially (the tape exists); not registered by Claude's choice.
- 2026-10-11 (LM-1 grading): C5 fires on both spreads (N=56, +1.10pp) and totals (N=24, +0.65pp).
  The totals-Over subset (N=14, +1.06pp) is small but directionally consistent. A "totals-only
  shade" sub-cell was not registered and is not added here. Testable for free: yes, the tape
  exists.
- 2026-10-11 (LM-1 grading): The C2 cross-point CLV issue — Cowork did not anticipate that C2
  fires at different points by definition, making de-vigged prob CLV an invalid measure. A
  point-based CLV metric was not registered. This is a registry design gap that affects the
  final grade of C2.
