# NHL Archetype Data Audit — Phase 0

**Date:** 2026-04-06
**Seasons:** 2021-22 through 2025-26 (6,476 games, 5 full seasons)

---

## Verdict: GO NOW

The NHL data pipeline already contains rich, 100%-coverage process-stat features
across 5 seasons that are well-suited for non-Vegas archetype construction.
No additional data pull is needed.

---

## Part 1 — File / Column Audit

### Primary Files

| File | Shape | Seasons | Level |
|------|-------|---------|-------|
| `nhl/nhl_games_canonical.csv` | 6,476 × 62 | 2021-2025 | Game-level |
| `nhl/nhl_feature_table.parquet` | 6,476 × 54 | 2021-2025 | Game-level (with rolling features) |
| `nhl/nhl_decisions.parquet` | varies | 2021-2025 | Game-level (model outputs) |
| `nhl/nhl_market_snapshots.parquet` | varies | 2025 | Game-level (odds) |

### Process-Stat Coverage (100% across all 5 seasons)

**A) Shot Generation Style**

| Column | Source | Coverage | Description |
|--------|--------|----------|-------------|
| `home/away_corsi_pct` | Canonical | **100%** | Shot attempt share (5v5 proxy) |
| `home/away_fenwick_pct` | Canonical | **100%** | Unblocked shot attempt share |
| `home/away_xgoals` | Canonical | **100%** | Expected goals for (MoneyPuck) |
| `home/away_xgoals_against` | Canonical | **100%** | Expected goals against |
| `home/away_shots_on_goal` | Canonical | **100%** | Shots on goal |
| `home/away_hd_shots` | Canonical | **100%** | High-danger shots for |
| `home/away_hd_shots_against` | Canonical | **100%** | High-danger shots against |
| `home/away_xgf_rolling_20` | Feature table | **100%** | Rolling 20-game xGF |
| `home/away_xga_rolling_20` | Feature table | **100%** | Rolling 20-game xGA |
| `home/away_shots_for_rolling_20` | Feature table | **100%** | Rolling 20-game shots for |
| `home/away_shots_against_rolling_20` | Feature table | **100%** | Rolling 20-game shots against |
| `home/away_hd_shots_for_rolling_20` | Feature table | **100%** | Rolling 20-game HD shots for |
| `home/away_hd_shots_against_rolling_20` | Feature table | **100%** | Rolling 20-game HD shots against |

**Status: AVAILABLE — all key shot generation / suppression features at 100% coverage**

**B) Transition / Event Shape**

| Feature | Available? | Notes |
|---------|-----------|-------|
| `home/away_shot_pressure` | Feature table | **100%** — shots for/against ratio (event volume proxy) |
| `home/away_hd_pressure` | Feature table | **100%** — HD shots for/against ratio (danger intensity) |
| Rush chances | NOT directly available | Would need play-by-play data (not in current pipeline) |
| Rebound chances | NOT directly available | Would need shot-sequence data |
| First-period tempo | NOT directly available | Period-level data not stored |

**Status: PARTIAL — event-rate proxies available via pressure features, but no period-level or transition-level detail**

**C) Defensive Structure Style**

| Feature | Available? | Derivation |
|---------|-----------|------------|
| Shot suppression rate | **DERIVABLE** | shots_against_rolling_20 |
| xG suppression | **DERIVABLE** | xga_rolling_20 |
| HD suppression | **DERIVABLE** | hd_shots_against_rolling_20 |
| HD danger concentration | **DERIVABLE** | hd_shots_against / shots_against (proportion of danger in total shots) |
| Penalty kill | **AVAILABLE** | pk_pct_rolling_20 |
| Passive vs aggressive | **DERIVABLE** | shot_pressure ratio: low volume + low danger = passive, high volume + low danger = aggressive |

**Status: AVAILABLE — can cleanly distinguish suppression styles**

**D) Goalie Workload Context**

| Feature | Available? | Notes |
|---------|-----------|-------|
| `home/away_goalie_sv_pct_rolling_10` | **100%** | FORBIDDEN for archetype input (market proxy) |
| `home/away_goalie_fatigue` | **100%** | Workload context — ALLOWED |
| `home/away_goalie_b2b` | **100%** | Back-to-back flag — ALLOWED |
| `home/away_backup_flag` | **100%** | Starter vs backup — ALLOWED |
| `home/away_goalie_vs_team_baseline` | **100%** | Matchup context — ALLOWED |
| Shots faced context | **DERIVABLE** | From shots_against_rolling + hd_pressure |

**Status: AVAILABLE — goalie workload descriptors accessible, save percentage excluded per rules**

### Derivable Archetype Inputs (from canonical, per-game)

| Derived Feature | Formula | Coverage | Distribution |
|----------------|---------|----------|-------------|
| shot_share | SOG / (SOG + opp_SOG) | 97% | mean=.511, std=.081 |
| xg_share | xGF / (xGF + xGA) | 97% | mean=.521, std=.117 |
| hd_share | HD_for / (HD_for + HD_against) | 97% | mean=.491, std=.241 |
| hd_rate (danger concentration) | HD_shots / SOG | 97% | mean=.108, std=.066 |
| corsi_pct | Already in canonical | 97% | mean=.511, std=.081 |

---

## Part 2 — Archetype Feasibility

### 1. SHOT GENERATION ARCHETYPES — LIKELY VIABLE

**Candidate inputs:** xGF rolling, shots_for rolling, hd_shots_for rolling, shot_pressure, hd_pressure

Can distinguish:
- **HIGH_VOLUME_PERIMETER:** High shots_for, low hd_rate → teams that generate many low-danger chances
- **LOW_VOLUME_HIGH_DANGER:** Low shots_for, high hd_rate → teams that generate fewer but more dangerous chances
- **BALANCED:** Moderate across both dimensions

**Viability: HIGH** — all inputs at 100% coverage, rolling features already built

### 2. DEFENSIVE STRUCTURE ARCHETYPES — LIKELY VIABLE

**Candidate inputs:** xGA rolling, shots_against rolling, hd_shots_against rolling, hd_pressure (defensive)

Can distinguish:
- **SHOT_SUPPRESSOR:** Low shots_against, low hd_against → teams that limit volume and danger
- **BEND_NOT_BREAK:** High shots_against, low hd_against → teams that allow volume but not danger
- **POROUS:** High shots_against, high hd_against → teams that allow both

**Viability: HIGH** — same coverage, same rolling infrastructure

### 3. GOALIE WORKLOAD REGIMES — MAYBE VIABLE

**Candidate inputs:** goalie_fatigue, backup_flag, goalie_b2b, shots_against context

Can distinguish:
- **SHELTERED:** Low shots_against, low hd_pressure → defense protects goalie
- **HIGH_WORKLOAD:** High shots_against, high hd_pressure → goalie faces heavy load
- **BACKUP_STATE:** Backup flag active → fundamentally different expectation

**Viability: MODERATE** — data exists but goalie state already used in live model. Risk of redundancy with existing pipeline features.

---

## Part 3 — Vegas-Proxy Risk

| Archetype Family | Vegas-Proxy Risk | Why |
|-----------------|-----------------|-----|
| **Shot Generation (offense)** | **MEDIUM** | xGF correlates with scoring, which Vegas prices. But HOW teams generate xG (volume vs danger) is less obviously priced. |
| **Defensive Structure** | **LOW-MEDIUM** | Shot suppression style is more distinct from market pricing than raw defensive quality. Markets price goals against; suppression SHAPE is less directly captured. |
| **Goalie Workload** | **HIGH** | Goalie quality is well-priced. Workload descriptors overlap with what markets already consider. |

**Rank by distinctness from Vegas:**
1. **Defensive Structure** (lowest proxy risk) — HOW teams suppress is less obvious than HOW MUCH
2. **Shot Generation Shape** (moderate proxy risk) — volume vs danger distinction has some independence
3. **Goalie Workload** (highest proxy risk) — markets already adjust for goalie context

---

## Part 4 — Recommended First Branch

### Test DEFENSIVE STRUCTURE ARCHETYPES first

**Why:**
1. **Lowest Vegas-proxy risk** — markets price goals against and save percentage, but the shot-suppression SHAPE (volume vs danger vs both) is less directly priced
2. **Clear mechanism for totals** — two teams with identical xGA can create very different game environments depending on whether they suppress through low volume or low danger. A low-volume suppressor facing a high-volume generator creates a specific game shape.
3. **100% data coverage** — all inputs available across 5 seasons, rolling features already built
4. **Interpretable clusters** — SUPPRESSOR vs BEND_NOT_BREAK vs POROUS is immediately understandable

**Minimum viable input set:**
- `shots_against_rolling_20` (volume)
- `hd_shots_against_rolling_20` (danger)
- `xga_rolling_20` (expected goals allowed)
- Derived: `hd_danger_rate = hd_against / shots_against` (danger concentration)

**Test design:**
1. Cluster teams into 3 defensive archetypes (K=3)
2. Test matchup cells: offensive archetype × defensive archetype
3. Check whether specific matchup cells have totals residuals vs market close
4. Control for obvious context (full-game total, goalie state, rest)

---

## Verdict: GO NOW

All process-stat inputs needed for defensive structure archetypes are available
at 100% coverage across 5 seasons with rolling features already computed.
No additional data pull or feature engineering is required before testing.
