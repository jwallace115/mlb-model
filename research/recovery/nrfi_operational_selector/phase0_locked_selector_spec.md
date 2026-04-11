# NRFI Operational Selector — Locked Spec (V1)

**Locked:** 2026-04-11
**Object ID:** `mlb_nrfi_selector_v1_20260411`
**Ruleset Version:** `frozen_v1`

---

## Selector Rules (FROZEN — do not modify without full revalidation)

### QUALIFY
- F5 closing total <= 4.0

### DISQUALIFY
- Night game AND F5 closing total = 4.0 exactly

### RANK
1. F5 total ascending (lower = better)
2. Tie-break: game start time ascending (earlier = first)
3. Tie-break: matchup string alphabetical

### CARD
- Top 3 selections
- Alternate #4 logged but not pushed

---

## Evidence Base

### Phase 4 (2026-04-11)
- V1 selector: 34.9% top-3 hit rate (+9.7pp vs 25.2% random baseline)
- V1 selector: 23.5% top-4 hit rate (+7.5pp vs 16.0% random baseline)
- Adding complexity (V2, V3) **hurt** performance
- Data: 9,900 games (2022-2026), 6,635 with F5 lines

### Phase 5 (2026-04-11)
- Logistic regression engines A-D tested against frozen V1
- No engine beat V1 on validation
- Selector remains recommended

---

## Input Sources

| Input | Source | Path |
|-------|--------|------|
| F5 closing total | Odds API F5 pull | `mlb_sim_f5/data/f5_lines_2026.parquet` |
| Day/night flag | MLB Stats API `dayNight` field | Live API call |
| Game identity | MLB Stats API schedule | Live API call |
| NRFI result | MLB Stats API linescore (1st inning) | Live API call |

## Join Key
- `game_id` in F5 parquet = `gamePk` in MLB Stats API (both are integer game PKs stored as strings)

## Team Abbreviation Note
- F5 data uses: ARI, OAK, CHW, KCR, TBR, SFG, WSN, SDP
- MLB API uses: AZ, ATH, CWS, KC, TB, SF, WSH, SD
- Join on game_id/gamePk, not team abbreviations
- Display uses F5 abbreviations (consistent with rest of model)
