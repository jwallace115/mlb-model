# P09 Standalone Shadow Tracker — Specification V1

**Date:** 2026-05-12
**Source:** MLB System Registry V2, P09 post-registry decision review
**Authorization:** Shadow specification only. No live betting. No promotion. No code implementation.

---

## 1. Executive Decision

- P09 is approved for standalone shadow specification only.
- P09 is **not** approved for live betting.
- P09 is **not** approved for promotion.
- P09 is **not** a V1 resurrection path. P09 operates independently of V1.
- P09 host placement (Mac vs VM) is **not decided** in this spec.
- P09 cron/launchd cadence is **not decided** in this spec.
- P09 canonical sportsbook is **not decided** in this spec.

---

## 2. System Identity

| Field | Value |
|---|---|
| **System name** | P09 — Contact Suppression UNDER Shadow |
| **Market** | Full-game totals UNDER |
| **Direction** | LOW P09 score → UNDER |
| **Formula** | `P09 = avg(home_hard_hit_rate, away_hard_hit_rate) * park_run_factor` |
| **Frozen cutoff** | P09 ≤ 31.7305 → signal fires (2024 bottom-20th-percentile) |
| **Config path** | `mlb_sim/pipeline/p09_overlay_config.json` |
| **Validation artifact** | `research/signal_scanner/p09_revalidation.md` — ADVANCE 5/5 |
| **Current registry status** | VALIDATED_SHADOW (PAUSED with V1) — to be reclassified upon standalone build |

---

## 3. Runtime Inputs

| Input | Definition | Source | PIT-safety requirement |
|---|---|---|---|
| `home_hard_hit_rate` | Home starter's rolling 5-start mean hard-hit rate allowed | Pitcher Statcast aggregate, shift(1) rolling(5, min_periods=3) | Must use only starts with `game_date < today` |
| `away_hard_hit_rate` | Away starter's rolling 5-start mean hard-hit rate allowed | Same | Same |
| `park_run_factor` | Home park runs factor (100 = neutral) | `config.STADIUMS[home_team]["park_factor"]` | Static; no PIT concern |
| `game_date` | Today's date | Schedule API | N/A |
| `game_id` / `game_pk` | Game identifier | Schedule API | N/A |
| `home_team`, `away_team` | Team abbreviations | Schedule API | N/A |
| `home_starter`, `away_starter` | Probable pitcher name + ID | Schedule API | Pregame only; if unavailable, skip game |
| `market_total` | Sportsbook closing/posted full-game total | Odds API or existing line capture | Capture timestamp required |
| `actual_total` | Final combined score | MLB Stats API (post-game) | Grading only |

---

## 4. Data-Source Decision

**Research file used by current P09 overlay:**
`research/statcast_enrichment/pitcher_statcast_per_start_starters_only.parquet` — max date 2025-09-28. Historical research artifact. Not daily-refreshed.

**Daily-refreshed file:**
`research/statcast_enrichment/pitcher_statcast_per_start.parquet` — rebuilt daily by `rebuild_statcast_aggregates.py`. Contains all pitchers (starters + relievers).

**Requirements for standalone tracker:**
- Must use the daily-refreshed Statcast file, not the stale research artifact.
- Must filter to starters only. Starter identification must be verified before implementation.
- Starter identification approach: either (a) join to `pitcher_game_logs.parquet` on `starter_flag=1`, or (b) use a minimum-pitches threshold per game. The approach must be documented and verified to match the research file's starter definition.
- Do not assume the VM has the correct Statcast parquet at runtime unless file-sync timing is verified.

---

## 5. PIT-Safety Requirements

The standalone tracker must enforce:

1. `shift(1)` — exclude the current game's start from the rolling window
2. `rolling(5, min_periods=3)` — 5-start rolling mean with minimum 3 starts required
3. No same-game Statcast leakage — today's game stats must not be included in today's feature
4. No post-game starter enrichment — starter identity must be known pregame
5. If starter identity is unavailable pregame, skip game with note `STARTER_UNAVAILABLE`
6. Separate verification required for:
   - Historical construction (does the research Statcast file use the same rolling spec?)
   - Same-day runtime construction (does the daily rebuilt parquet preserve shift(1) semantics?)

---

## 6. Standalone Runner Design

**Proposed future script path:** `mlb/pipeline/p09_shadow_daily.py`

Path mirrors `yrfi_shadow_daily.py`. Host placement and cadence are NOT DECIDED in this spec. Future implementation must apply ops v9 §15 host-placement logic.

**The future runner should:**
1. Load today's MLB schedule (via `modules.schedule.fetch_schedule` or MLB Stats API)
2. Identify probable starters (from schedule data)
3. Load pitcher Statcast aggregate (daily-refreshed file)
4. Filter to starters, compute shift(1) rolling 5-start hard_hit_rate per pitcher
5. Look up park_run_factor from `config.STADIUMS`
6. Compute P09 score: `avg(home_hh_r5, away_hh_r5) * park_rf`
7. Flag games where P09 ≤ 31.7305
8. Record sportsbook total/price if available (source TBD)
9. Write shadow output to `mlb/logs/p09_shadow_2026.json`
10. **Not call V1.** Not import `daily_signal_generator.py`. Not require any V1 output.

---

## 7. Output Schema

**Proposed output path:** `mlb/logs/p09_shadow_2026.json`

Each entry (one per game where P09 can be computed):

```
{
  "date": "YYYY-MM-DD",
  "game_id": "string or int",
  "away_team": "ABB",
  "home_team": "ABB",
  "away_starter": "Name",
  "home_starter": "Name",
  "away_starter_id": int,
  "home_starter_id": int,
  "away_hard_hit_rate_rolling5": float or null,
  "home_hard_hit_rate_rolling5": float or null,
  "park_run_factor": int,
  "p09_score": float or null,
  "cutoff": 31.7305,
  "signal_fired": true/false,
  "market_total": float or null,
  "sportsbook": "string or null — NOT DECIDED",
  "price_over": int or null (American),
  "price_under": int or null (American),
  "alt_books": [],
  "selected_side": "UNDER" or null,
  "actual_total": int or null,
  "result": "W" / "L" / "P" / null,
  "graded": true/false,
  "graded_date": "YYYY-MM-DD" or null,
  "created_at": "ISO timestamp",
  "data_version": "p09_shadow_v1",
  "pit_safety_flags": {
    "shift1_applied": true/false,
    "rolling_window": 5,
    "min_periods": 3,
    "starter_source": "description"
  },
  "notes": []
}
```

**Sportsbook fields:**
- `sportsbook` = canonical book for shadow tracking. Canonical book is NOT DECIDED in this spec.
- `alt_books` = optional array of `{book, market_total, price_over, price_under, timestamp}` for forensic comparison.
- Implementation must not silently default to a book without a decision.

---

## 8. Grading Design

- Grade after game reaches Final status via MLB Stats API
- `actual_total` = `home_score + away_score`
- `selected_side` = UNDER when `signal_fired = true`
- Result:
  - W if `actual_total < market_total`
  - L if `actual_total > market_total`
  - P if `actual_total == market_total`
- Record closing-line or captured-line basis with timestamp
- Do not mix proxy and real-price economics without labeling
- If multiple books captured, canonical-book ROI and alt-book forensic ROI must be labeled separately in any performance analysis

---

## 9. Dashboard / Consumer

- Add to MLB tracker/performance section
- Clearly labeled **"P09 Shadow — Not Live"**
- Show: N, hit rate, ROI (if real prices), push count, monthly split
- Do not show as official betting card
- Do not surface on home tab signal count

---

## 10. Gate Structure

### Review gate (interim check, no promotion)
- **Trigger:** N ≥ 50 graded real-price shadow signals
- **Output:** Progress report only
- Check early ROI, hit rate, pushes, monthly split, data quality
- No live activation from this gate

### Promotion-consideration gate (decision pass eligible)
- **Trigger:** N ≥ 100 graded real-price shadow signals
- ROI > +3% at captured UNDER prices
- Hit rate above blind UNDER baseline by meaningful margin
- Non-collapsing monthly split
- PIT safety verified for both historical and runtime construction
- Research/live identity MATCH confirmed
- No benchmark-only proxy economics

### Live activation gate (separate future approval)
- Real-price economic gate satisfied
- Registry updated to reflect standalone P09 status
- Separate decision review completed
- Explicit Jeff approval
- No auto-promotion

---

## 11. Kill Gates

Signal must be killed (shadow terminated) if any of these occur:

- N ≥ 50 and ROI < -5%
- Directional reversal (HIGH P09 values → UNDER, contradicting research)
- Monthly collapse (≥3 consecutive negative months after N ≥ 30)
- PIT-safety failure discovered in either historical or runtime construction
- Starter feature identity mismatch between research and live computation
- Research/live formula mismatch (P09 score diverges from `p09_overlay.py` on same inputs)
- Canonical-book price capture failure (>20% of games missing prices after 30 days)

---

## 12. Open Questions

1. **Can daily Statcast file reliably isolate starters?** The daily rebuild (`pitcher_statcast_per_start.parquet`) includes all pitcher appearances ≥30 pitches. Need to verify whether filtering by join to `pitcher_game_logs.parquet` (starter_flag=1) or by game-level pitch count threshold matches the research starters-only file.

2. **Are probable starters available early enough?** The MLB Stats API schedule endpoint provides probable pitchers, but availability varies. If starters aren't posted until close to game time, the runner may need a late-morning cadence.

3. **Which sportsbook is canonical for P09 shadow tracking?**
   - Hard Rock is the user's practical primary book.
   - DraftKings may have wider historical/API coverage.
   - Pinnacle may be useful for CLV benchmarking.
   - Decision required before implementation.

4. **Should alt-book prices be captured for forensic comparison?** Adds API cost but provides portability evidence.

5. **Where does the runner live: Mac or VM?**
   - Mac may be required if Statcast parquet is Mac-canonical (rebuild_statcast_aggregates runs on Mac at 4:45am).
   - VM may be acceptable if git/file-sync timing ensures the daily parquet is available before P09 cron fires.

6. **If VM: does push_daemon.sh timing make the Statcast parquet available before P09 cron fires?** The Statcast rebuild pushes via `git_push.sh` from the Mac. The VM picks up via `push_daemon.sh` every 30 minutes. If P09 fires at 7:30am on VM, the Mac rebuild at 4:45am + push + daemon cycle should have the parquet ready — but this timing needs verification.

7. **What cadence should P09 use?** Daily pre-game is sufficient for shadow. Per-snapshot is unnecessary for a pregame-only signal.

8. **Is `market_total` captured before first pitch?** P09 needs the closing/posted total for grading. This may come from the existing line snapshot infrastructure or require a new pull.

9. **Does P09 work at real prices, not just closing-total proxy?** The validation used closing totals (actual vs line), not bet-level ROI at sportsbook vig. Shadow tracking with real prices will answer this.

10. **Should P09 be a standalone UNDER selector or only an amplifier?** The research validated P09 as a standalone predictor (ADVANCE 5/5, independent=YES). The current overlay code only amplifies V1 UNDER. The standalone shadow should test standalone UNDER selection to determine if P09 has independent edge.

---

## 13. Implementation Hard Stops

Future implementation must stop and report if any of these occur:

- Starter rolling hard-hit feature cannot be reproduced PIT-safely from daily data
- P09 score cannot be matched to `p09_overlay.py` `compute_p09()` on sample historical games
- Output schema cannot be populated (missing fields, wrong types)
- Grading cannot distinguish proxy vs real-price basis
- Runner requires V1 (`daily_signal_generator.py`) to execute
- Host placement cannot be justified under ops v9 §15
- Canonical sportsbook cannot be identified or labeled
- Market timestamp cannot be captured or labeled
- Any open question from Section 12 blocks implementation and has not been answered
