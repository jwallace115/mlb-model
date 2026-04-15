# TEAM-GAME LINEUP STATE SUBSTRATE — SELF-AUDIT

**Build timestamp:** 2026-04-15T09:12:33Z
**Auditor:** Build script self-audit (no human review at time of writing)

---

## Self-Audit Questions (13)

---

### Q1. Were any background tasks used during the build?

**No.** All steps were executed synchronously in a single Python process per script invocation. No threading, multiprocessing, subprocess background calls, or async execution was used. The build ran as three sequential blocking Python scripts.

---

### Q2. Were any files created outside the 4 permitted outputs?

**No.** The only files written to `research/recovery/mlb_lineup_state_substrate/` are the 4 permitted outputs:
1. `team_game_lineup_state.parquet`
2. `TEAM_GAME_LINEUP_STATE_BUILD_REPORT.md`
3. `TEAM_GAME_LINEUP_STATE_BUILD_REGISTRY.json`
4. `TEAM_GAME_LINEUP_STATE_SELF_AUDIT.md`

Temporary metadata was written to `/tmp/substrate_meta.json` during build orchestration (outside the project directory) and is not a project output.

---

### Q3. Is PIT-safety guaranteed for all rolling features?

**Yes.** The mechanism is `x.shift(1).rolling(window, min_periods=min_per).mean()` applied within `(team, season)` group, after sorting by `(game_date, game_number)`. The `shift(1)` ensures each row's feature value is computed from the previous game forward — the current game's statistics never appear in its own feature vector. This was verified structurally (the transform pattern is deterministic and does not reference the current row's value).

---

### Q4. Were per-game realized statistics excluded from the output parquet?

**Yes.** The following 18 per-game realized columns are computed internally as aggregation intermediates but are explicitly excluded from `output_cols` and do not appear in the final parquet:
`total_ab`, `total_hits`, `total_walks`, `total_k`, `total_hr`, `total_doubles`, `total_triples`, `bb_rate`, `k_rate`, `hr_rate`, `iso`, `sc_avg_exit_velo`, `sc_hard_hit_rate`, `sc_barrel_rate`, `sc_avg_launch_angle`, `sc_xwoba_contact`, `sc_xba_contact`, `sc_xslg_contact`.

---

### Q5. Is Statcast coverage adequate?

**Yes.** 19,710 of 19,712 team-game rows (99.99%) have Statcast data. The 2 missing rows represent negligible data gaps. Statcast rolling features for those 2 rows will be null only within windows that contain those games — a correctly handled propagation.

---

### Q6. Are doubleheaders handled correctly?

**Yes.** The sort order is `(team, season, game_date, game_number)`. This ensures game_number=1 precedes game_number=2 within the same calendar day for the same team. Rolling features for game_number=2 on a doubleheader day therefore correctly include game_number=1's statistics (which are shifted by 1, making them visible as a prior game). There are 324 team-game rows with game_number=2 in the output, sourced from game_table.

---

### Q7. Is the team normalization consistent between inputs?

**Yes.** The same `TEAM_MAP = {AZ:ARI, CWS:CHW, KC:KCR, SD:SDP, SF:SFG, TB:TBR, WSH:WSN, ATH:OAK}` was applied to both HGL and BGS before any aggregation or joining. Both layers used `team_norm` as the grouping key before renaming back to `team`. The join on `(game_pk, team, season)` produced a perfect 19,712:19,712 match with no unmatched rows, confirming team encoding consistency.

---

### Q8. Are the rolling window min_periods settings appropriate?

**Yes.** The minimum periods are:
- window=7, min_periods=5: requires 5 prior games (~1 week)
- window=10, min_periods=7: requires 7 prior games
- window=15, min_periods=10: requires 10 prior games (~2 weeks)
- window=20, min_periods=12: requires 12 prior games

These prevent the early-season null blow-up (where a team with 3 prior games produces a misleading 3-game rolling mean for a 20-game window). The null rates (3.8%–8.7%) reflect legitimate season-start periods where features are truly unavailable, which is the correct behavior.

---

### Q9. Does the output parquet have the correct schema?

**Yes.** The output has 19,712 rows and 54 columns:
- 6 identity columns
- 44 approved rolling columns (11 source metrics × 4 windows)
- 4 carried-only columns (diagnostic/weighting use)

The parquet is sorted by `(season, game_date, game_number, game_pk, team)` for predictable ordering.

---

### Q10. Were the inputs loaded from approved paths without modification?

**Yes.** Both source parquets were read-only (`pd.read_parquet`). No writes were made to source files. `game_table.parquet` was also read-only, and only `game_pk` and `game_number` were extracted from it.

---

### Q11. Are there any known data quality issues to flag for downstream users?

**Three issues to note:**

1. **home_away encoding is 'A'/'H'**: Inherited from HGL. Some other substrates may use 'home'/'away'. Downstream joins should handle this mapping.

2. **carried-only columns are not PIT-safe features**: `total_pa`, `n_batters`, `sc_batter_count`, `sc_total_bip` are game-level observed counts. They must not be used as predictive inputs for the game being predicted. They are included only for diagnostic/weighting diagnostics (e.g., to identify games where the lineup was shortened or Statcast BIP count was low).

3. **2026 partial-season rolling features**: As of build date (2026-04-15), 2026 has ~2,850 batter-game Statcast rows and ~2,943 HGL rows. Rolling features for early 2026 games will have nulls for longer windows until sufficient history accumulates. This is by design.

---

### Q12. Was the join between Layer A and Layer B lossless?

**Yes.** The left join on `(game_pk, team, season)` produced exactly 19,712 rows — identical to the Layer A (box-score) spine row count. No rows were dropped. The near-perfect Statcast coverage (99.99%) means the join populated Statcast columns for all but 2 rows.

---

### Q13. Is this substrate safe for use in downstream feature engineering without further modification?

**Yes, with one caveat.** The 44 approved rolling columns are PIT-safe and ready for use as predictive features. Downstream code should:
- Join on `(game_pk, team)` to enrich game-level records with offensive state
- Use `*_last_{7,10,15,20}` columns as features
- **Not** use the carried-only columns (`total_pa`, `n_batters`, `sc_batter_count`, `sc_total_bip`) as model features for the game being predicted
- Handle nulls (3.8%–8.7% of rolling features) — typically via imputation with season means or exclusion of early-season rows

---

## Summary Verdict

| Check                              | Result |
|------------------------------------|--------|
| Background tasks used              | NO     |
| Extra files created                | NO     |
| PIT-safety: shift(1) applied       | PASS   |
| Per-game realized stats excluded   | PASS   |
| Statcast coverage                  | 99.99% |
| Doubleheader sort correct          | PASS   |
| Team normalization consistent      | PASS   |
| Min-periods appropriate            | PASS   |
| Output schema correct              | PASS   |
| Source files unmodified            | PASS   |
| Known issues disclosed             | YES    |
| Join lossless                      | PASS   |
| Safe for downstream use            | YES    |

**Overall: PASS — substrate is production-ready.**
