# Source Audit — TB Market Efficiency Study

## CRITICAL FINDING: Historical TB Prop Lines NOT Available

**No historical TB prop closing odds exist locally for 2024 or 2025.**

| Source | Available? | Contents |
|--------|-----------|----------|
| SQLite props table | YES — 1,171 TB rows | Projections only; 16 have lines (March 26-27 2026 only) |
| Batter boxscores (9,715 games) | YES | Actual TB per batter-game (from boxscores) |
| Odds API batter prop lines | NOT CACHED for TB | Only 2026 Spring Training forward |
| Batter props cache (2025) | YES — 631 players | Season stats only (SLG, barrel%, etc.) — no game-level lines |
| Props shadow system | YES | Focused on HITS market, not TB |

## What IS Available

### Actual TB outcomes (from boxscores, 2022-2025)
- ~174,870 batter-game rows with H, 2B, 3B, HR, total_bases
- Full lineup + batting order
- Opposing pitcher and park

### Batter quality features
- Rolling K%, BB%, contact%, ISO from V3 hitter profiles (174,870 rows)
- Season SLG, barrel%, hard_hit%, exit_velo from batter props cache (631 players, 2025 only)

### Pitcher / park / weather
- Full feature table with park factors, temperature, wind
- Pitcher Statcast per-start (hard_hit, barrel, whiff, zone rates)

## Implication for Study

**Cannot run a true market-efficiency study** (no historical odds to compare against).

**CAN run:**
1. TB outcome distribution analysis (what % of batters go over 1.5 TB by context)
2. Feature bucket scans using actual outcomes only (no ROI calculation against real odds)
3. Synthetic line efficiency test (construct fair O/U 1.5 at -110/-110 and test features against that)

The synthetic approach is weaker than real odds but can identify feature families worth modeling once real prop lines become available.
