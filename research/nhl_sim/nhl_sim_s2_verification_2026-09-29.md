# NHL sim S-WO2 — verification from the files (Cowork, 2026-09-29)

Branch `nhl/sim-s1` commits a1b02e7f6 (S7), 05ca72b48 (S8), f44c98853 (S9), f8fc2d24a (log). Checked from the
tables in `~/mlb-model-nhlsim1` and the JSON, not the report.

## Holds (recomputed independently)
- State time per game: 3,600-3,900 s for all 2,624 fit-season games (no shootout phantom time).
- Last span's score vs the final score, regulation games, all 6,560: 9 mismatches. 7 are a goal inside the final
  span, and 2 are the stale canonical rows 2025021229/1230 already noted. 99.8%.
- Score effects at 5v5 in the 3rd, per team per 60, rebuilt from shots + state_time with team-seconds:
  -2: 46.0 | -1: 44.1 | tied: 41.0 | +1: 37.2 | +2: 36.4 — identical to constants_v2 (the self-flagged
  "double-count" worry is not a defect: tied seconds count once per team, which is the right per-team
  denominator).
- Penalties 3.77 per team per game; pulls at -1 in the last 3:00 93.9% (n=1,056); shootout conversion 32.3%;
  OT decided in OT 66.6% — inside the pre-registered bands.

## Notes carried forward (not blockers)
- `score_effect_xg_mult_*` is GOALS per attempt relative to tied, not xG per attempt. The engine must use it
  under that meaning (it captures leading teams finishing better on the counter). Rename it in S-WO3.
- xg_v1.json was regenerated during S9 and no longer matches S5's sha256. v1 is superseded; nothing uses it.
- Not done, and not needed as constants: the share of minors ended early (the engine ends a minor on a PP goal by
  rule); goals/xG by MONTH (by season only: 0.981 / 1.018 / 1.003 / 1.012 / 1.068 — 2025-26 has 6.8% more goals
  than xG v2 expects, so the engine needs a point-in-time league finishing term; S-WO3 item 2).
- The goals-vs-box-score control was run on 6,218 cached box scores. Cowork's check against the canonical results
  covers all 6,560 (6,558 exact).

Verdict: S-WO2 holds. nhl/sim-s1 can merge (constants_v1 is marked withdrawn in the manifest).
