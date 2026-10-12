# FEATURE FAMILIES v1 (IE-D3) — 2026-10-11

## Fit-window rule

| Window | Seasons | Role | Status |
|--------|---------|------|--------|
| Discovery | 2021-2023 | Feature search, threshold tuning, archetype clustering | OPEN for IE-1 |
| Clean look | 2024 | One-shot validation; shared with the GL ledger | **UNTOUCHED** — no IE code has read 2024 target data |
| Not blind | 2025 | Available but contaminated by prior viewing in sim work | Excluded from validation claims |
| Forward | 2026+ | Live grading only | Append-only |

**Rule:** IE-1 may open 2021-2023 data for discovery. The 2024 season is the ONE
clean out-of-sample look. It is shared with the GL ledger's existing OOS window.
No IE code may read 2024 outcomes until the family priors are registered below
and Cowork has filled the prior column.

---

## Families

Each family uses only TIMESTAMPED or WEEK-KEYED sources from the IE-D1 inventory.
END-OF-SEASON sources (ref_crew_aggregates) are excluded by construction.

| # | Family | Source(s) | PIT | As-of rule | Mechanism | Target | Prior (Cowork, 2026-10-12) |
|---|--------|-----------|-----|-----------|-----------|--------|----------------------------------|
| F1 | **Injury trajectory** | injuries (#8) | TIMESTAMPED (`date_modified`) | Latest report with `date_modified < kickoff_utc` | A player moving Limited->Full or Full->Out across Wed-Fri reports signals recovery/deterioration that the market may price only at the final designation, missing the trajectory's information content. | outcome-vs-close | 20% — The market reads injury reports closely; the trajectory (Limited->Full across the week) is subtler and matters most for OL/secondary, where the market is laziest. |
| F2 | **Pass protection quality** | pfr_weekly_pass (#6) | WEEK-KEYED | Snap-weighted mean over players with >= 20 offensive snaps, by position group (QB, OL, WR/TE, RB), cumulative through week N-1 | Pressure rate and bad-throw % reveal offensive-line and QB quality not visible in yards/TDs. A team whose pressure rate spikes but whose scoring holds may be about to regress. | outcome-vs-close | 15% — Public and widely used by pricing models; little left. |
| F3 | **Scheme tendency shift** | ftn_charting (#1) | TIMESTAMPED (`date_pulled`, batch) | Snap-weighted mean over players with >= 20 offensive snaps, by position group (QB, OL, WR/TE, RB), cumulative through week N-1 | Play-action rate, RPO rate, motion rate, screen rate shift week-to-week. The market may anchor on season-long tendencies. A sudden increase in motion rate (correlated with offensive efficiency) may be under-priced. | outcome-vs-close | 15% — Real but slow-moving; the market anchors less than the mechanism assumes. |
| F4 | **Rushing efficiency (RYOE)** | ngs_rushing (#3) | WEEK-KEYED | Snap-weighted mean over players with >= 20 offensive snaps, by position group (QB, OL, WR/TE, RB), cumulative through week N-1 | Rush yards over expected (RYOE) separates scheme from talent. A team with negative RYOE but high raw yardage is scheme-dependent; the market may over-weight the raw number. | outcome-vs-close | 10% — NGS is public; rushing explains little margin variance. |
| F5 | **Receiving separation** | ngs_receiving (#4) | WEEK-KEYED | Snap-weighted mean over players with >= 20 offensive snaps, by position group (QB, OL, WR/TE, RB), cumulative through week N-1 | Average separation and cushion measure how well receivers get open independent of QB accuracy. High separation + low catch% = unlucky; the market may anchor on the low catch%. | outcome-vs-close | 10% — Same; a props input more than a sides input. |
| F6 | **Snap-count usage shift** | snap_counts (#5) | WEEK-KEYED | Snap-weighted mean over players with >= 20 offensive snaps, by position group (QB, OL, WR/TE, RB), week N-1 snap shares | A backup RB going from 15% to 40% offensive snaps signals a role change before the stat line shows it. The market prices the starter's projection, not the shift. | outcome-vs-close | 25% — Role changes do precede the stat line; the question is whether they move team margin or only props. |
| F7 | **Referee crew scoring** | officials (#7) + schedules (#11) | WEEK-KEYED | Season-to-date penalty/scoring stats for the assigned crew, using only completed games through week N-1; scored on totals as primary, margin as secondary | Referee crews have persistent penalty-rate tendencies that affect game pace. The market may treat all crews as neutral. | outcome-vs-close | 25% on TOTALS, 10% on margin — A known, persistent, partly-priced effect; totals only. |
| F8 | **Depth chart instability** | depth_charts (#10) | WEEK-KEYED (PIT WARNING: no within-week timestamp) | Week N-1 depth chart only; week N is never read (A2: the 2026-09-18 usage leak) | Multiple position changes between weeks signal roster churn. The market may not price the cumulative effect of 3+ starter changes across positions. | outcome-vs-close | 10% — Weak once the leak is removed; the signal was the leak. |
| F9 | **Rest + surface + weather** | schedules (#11) + wind_archive (#14) | WEEK-KEYED | Pre-game schedule data + forecast | Short rest (Thu game -> Sun game = 3 days) on grass after dome/turf, combined with wind forecast. Interaction of rest x surface x weather may be under-weighted vs the individual factors. | outcome-vs-close | 20% — Weather on totals is the strongest known public effect; the interaction is unproven. |
| F10 | **Opening-line movement** | line_movement (#12) + opening_lines_raw (#13) | WEEK-KEYED (snapshot ~5 days pre-game) | Opening total captured early-week; close from nflverse | Direction and magnitude of open-to-close movement. Large moves toward the over/under may signal informed money or overreaction. The residual (actual - close) conditioned on movement direction may reveal market over-correction. | close-vs-open AND outcome-vs-close | 20% — Movement predicts the close near-certainly; the residual over-correction is the C3/C4 story, which just failed interim. |

### IE-0 overall and sub-predictions (Cowork, 2026-10-12)

| ID | Prediction | Prior |
|----|-----------|-------|
| IE-0 (overall) | The combined layer beats the close on 2024 | 25% |
| IE-0b | At least one family individually clears t >= 2 on 2024 | 50% |
| IE-0c | The engine fed with the information layer beats the ridge fed with the same layer (the physics earn a place) | 15% |

Pre-registered null control for every fit: team labels shuffled within week; every family must read ~0 under it.

---

## Notes

1. **No family touches 2024 or later target data.** Discovery uses 2021-2023 only.
   The 2024 look is reserved for Cowork validation after priors are filled.

2. **F8 (depth charts) carries a PIT warning.** The nflverse depth chart snapshot
   has no within-week timestamp. A week-N depth chart may reflect Tuesday's or
   Saturday's version. **IE-D4 fix:** F8 now reads only week N-1 data; week N is
   never read, eliminating the 2026-09-18 usage leak. For live deployment, a
   real-time depth-chart feed would still be needed for sub-weekly resolution.

3. **F10 (line movement) targets both close-vs-open and outcome-vs-close.** The
   former measures whether the movement itself is informative; the latter measures
   whether the close over-corrects.

4. **All as-of rules use "through week N-1"** — prior-week data only. This ensures
   no same-week leakage. Injuries (F1) use the pre-kickoff timestamp filter instead,
   because injury reports update multiple times per week.

5. **Families F2-F6 aggregation (IE-D4 fix):** snap-weighted mean over players
   with >= 20 offensive (or defensive, for defensive families) snaps in that week,
   by position group (QB, OL, WR/TE, RB; DL, LB, DB), computed through week N-1.
   This is now fixed, not a discovery decision.

6. **Sources excluded by construction:**
   - `ref_crew_aggregates.csv` — END-OF-SEASON aggregate, no week key
   - `nfl_wind_forecast_pit_2024.parquet` — 2024-only, single-season
   - PBP (`pbp_20XX.parquet`) — not a family source directly, but available for
     derived features if needed. PIT note: PBP is revised post-season (EPA corrections).
     Any PBP-derived feature must use only data available before the game in question.
