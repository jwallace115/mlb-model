# NCAAF Transfer Portal Shock — Early-Season Spread Mispricing

**Research date:** 2026-04-08
**Seasons:** 2022, 2023, 2024, 2025
**Scope:** Weeks 1-4 FBS games with available spread data

---

## Phase 0 — Data Audit

### Sources available
| Source | Status | Notes |
|--------|--------|-------|
| CFBD API (`/player/portal`) | Active | 12,652 transfers across 2022-2025; star ratings on 97% |
| CFBD API (`/player/returning`) | Active | Returning production (percentPPA) for 528 team-seasons |
| CFBD games (local parquet) | 2022-2024 cached | 11,240 games in `research/ncaaf/cfbd_games.parquet` |
| CFBD betting lines (local + API) | 2022-2025 | 2022-24 cached; 2025 pulled live (3,345 line rows) |
| CFBD SP+ ratings (local) | 2022-2024 | 401 team-season ratings |
| Odds API historical NCAAF | Backfilled 2022-2024 | Game markets in `data/odds_archive/ncaaf/` |
| CFBD API key | `.env` file | Confirmed working |

### Gap assessment
- Transfer portal data has `destination = None` for ~25% of 2022-2023 entries (players who entered portal but didn't land). This is expected and handled — they count as outgoing from origin only.
- Star ratings available for 97% of transfers. `rating` (0.0-1.0 composite) available for fewer (~50-70% depending on year). Analysis uses star ratings as the primary quality metric.
- Portal volume grows sharply: 2,273 transfers in 2022 to 4,499 in 2025.

---

## Phase 1 — Portal Shock Metric Construction

### Definitions

For each FBS team-season, computed from CFBD `/player/portal`:

| Metric | Definition |
|--------|-----------|
| `portal_in_count` | Number of incoming transfers with this team as destination |
| `portal_out_count` | Number of outgoing transfers with this team as origin |
| `portal_in_stars` | Sum of star ratings (1-5) of incoming transfers |
| `portal_out_stars` | Sum of star ratings (1-5) of outgoing transfers |
| `net_star_shock` | `portal_in_stars - portal_out_stars` |
| `total_transfers` | `portal_in_count + portal_out_count` |
| `percentPPA` | Returning production percentage (from CFBD `/player/returning`) |

### Distribution

544 FBS team-seasons with portal metrics across 2022-2025.

Pooled quartile thresholds:
- `net_star_shock`: Q25 = -28.0, Q75 = -3.0
- `total_transfers`: Q25 = 21, Q75 = 44

Note: net_star_shock is generally negative because outgoing transfers (which count as star loss) often outnumber resolved incoming transfers in the data. The relative ranking is what matters.

---

## Phase 2 — Bucket Definitions

| Bucket | Definition | N (team-seasons) |
|--------|-----------|:-:|
| NEGATIVE_SHOCK | Bottom quartile of net_star_shock (lost more talent than gained) | 149 |
| MIDDLE | Interquartile range | 255 |
| POSITIVE_SHOCK | Top quartile of net_star_shock (gained more talent than lost) | 140 |
| HIGH_TURNOVER | Top quartile of total transfers (most roster churn) | 140 |
| STABLE | Bottom quartile of total transfers (least roster churn) | 142 |

---

## Phase 3 — Early-Season ATS Results (Weeks 1-4)

**Sample: 2,381 team-game observations (pushes excluded) across 2022-2025**

### By Net Star Shock Bucket

| Bucket | N | ATS Cover | Cover % | Mean ATS Margin |
|--------|:-:|:---------:|:-------:|:---------------:|
| NEGATIVE_SHOCK | 665 | 355 | **53.4%** | **+1.33** |
| MIDDLE | 1,123 | 541 | 48.2% | -0.39 |
| POSITIVE_SHOCK | 593 | 303 | 51.1% | +0.50 |

**Key finding:** Teams that lost the most talent via the portal (NEGATIVE_SHOCK) *cover* at 53.4% in Weeks 1-4, outperforming baseline by 3.4 points. This is counterintuitive — the market appears to *overcorrect* for portal losses, making these teams too cheap.

### Season-by-Season Stability (NEGATIVE_SHOCK)

| Season | N | Cover % | ATS Margin |
|:------:|:-:|:-------:|:----------:|
| 2022 | 204 | 55.4% | +1.17 |
| 2023 | 174 | 51.7% | +0.94 |
| 2024 | 145 | 51.0% | +1.12 |
| 2025 | 142 | 54.9% | +2.23 |

Direction is consistent all four seasons. Magnitude varies.

### By Total Turnover Bucket

| Bucket | N | Cover % | ATS Margin |
|--------|:-:|:-------:|:----------:|
| STABLE | 587 | 46.3% | -0.43 |
| MODERATE | 1,185 | 50.5% | -0.18 |
| HIGH_TURNOVER | 609 | **53.9%** | **+1.97** |

High-turnover teams (most total portal activity, in + out) cover at the highest rate. This aligns with the NEGATIVE_SHOCK finding — the market penalizes roster upheaval, but chaotic rosters actually outperform the spread.

---

## Phase 4 — Controls

### By Spread Band (NEGATIVE_SHOCK, Weeks 1-4)

| Spread Band | N | Cover % | ATS Margin |
|:-----------:|:-:|:-------:|:----------:|
| Pick to -7 | 209 | 55.0% | +1.99 |
| -7 to -14 | 151 | 48.3% | -0.52 |
| -14 to -21 | 96 | 54.2% | +1.59 |
| -21+ | 209 | 55.0% | +1.87 |

Effect persists in close games and large spreads. The 7-14 band is the weakest, but N is modest.

### By Home / Away

| Bucket | Venue | N | Cover % | ATS Margin |
|--------|:-----:|:-:|:-------:|:----------:|
| NEGATIVE_SHOCK | Home | 406 | 53.0% | +1.49 |
| NEGATIVE_SHOCK | Away | 259 | 54.1% | +1.07 |
| POSITIVE_SHOCK | Home | 328 | 55.5% | +1.61 |
| POSITIVE_SHOCK | Away | 265 | 45.7% | -0.87 |

NEGATIVE_SHOCK covers regardless of venue. Interesting: POSITIVE_SHOCK teams (talent gainers) show a strong home/away split — they cover at home (55.5%) but fail away (45.7%), possibly reflecting new rosters performing better in familiar environments.

### By Conference Tier

| Bucket | Tier | N | Cover % | ATS Margin |
|--------|:----:|:-:|:-------:|:----------:|
| NEGATIVE_SHOCK | P5 | 378 | 53.7% | +1.35 |
| NEGATIVE_SHOCK | G5 | 287 | 53.0% | +1.29 |
| POSITIVE_SHOCK | P5 | 98 | 46.9% | -1.15 |
| POSITIVE_SHOCK | G5 | 495 | 51.9% | +0.83 |

NEGATIVE_SHOCK effect survives at both P5 and G5 level. Interestingly, POSITIVE_SHOCK P5 teams (elite programs loading up on transfers) actually *undercover* — the market may overrate their portal hauls.

---

## Phase 5 — Mispricing Characterization

### NEGATIVE_SHOCK: Favorite vs Underdog

| Role | N | Cover % | ATS Margin |
|:----:|:-:|:-------:|:----------:|
| Favorite | 409 | **55.3%** | +1.83 |
| Underdog | 256 | 50.4% | +0.53 |

The strongest signal is when NEGATIVE_SHOCK teams are *favorites*. The market shades the line toward their opponent (because of portal losses), but the team still wins by more than expected. Binomial test: p = 0.038.

### POSITIVE_SHOCK: Favorite vs Underdog

| Role | N | Cover % | ATS Margin |
|:----:|:-:|:-------:|:----------:|
| Favorite | 336 | 51.2% | +0.70 |
| Underdog | 257 | 51.0% | +0.24 |

No meaningful split for POSITIVE_SHOCK teams.

---

## Phase 6 — Fade Curve

### NEGATIVE_SHOCK ATS Through Season

| Window | N | Cover % | ATS Margin |
|:------:|:-:|:-------:|:----------:|
| Weeks 1-2 | 398 | 53.0% | +1.96 |
| Weeks 3-4 | 267 | 53.9% | +0.38 |
| Weeks 5-8 | 479 | 48.9% | -0.46 |
| Weeks 9-16 | 735 | 47.3% | -0.59 |

Clear fade: the effect is concentrated in Weeks 1-4 and *reverses* by mid-season. This is the signature of an early-season market adjustment lag — the market eventually corrects, and by mid-season these teams are correctly priced (or even slightly overvalued as the market catches up).

### POSITIVE_SHOCK ATS Through Season

| Window | N | Cover % | ATS Margin |
|:------:|:-:|:-------:|:----------:|
| Weeks 1-2 | 361 | 51.5% | -0.06 |
| Weeks 3-4 | 232 | 50.4% | +1.37 |
| Weeks 5-8 | 416 | 50.2% | +0.45 |
| Weeks 9-16 | 678 | 52.9% | +0.50 |

No clear fade pattern — POSITIVE_SHOCK does not show a distinct early-season dislocation.

---

## Composite: Shock + Returning Production

| Shock Bucket | Returning Prod | N | Cover % | ATS Margin |
|:------------:|:--------------:|:-:|:-------:|:----------:|
| NEGATIVE_SHOCK | Low return | 303 | 52.1% | +0.89 |
| NEGATIVE_SHOCK | High return | 362 | **54.4%** | **+1.69** |
| POSITIVE_SHOCK | Low return | 298 | 52.3% | +1.19 |
| POSITIVE_SHOCK | High return | 266 | 48.1% | -0.76 |

The strongest cell: NEGATIVE_SHOCK + HIGH_RETURN (teams that lost transfers but retained core production). These cover at 54.4% with +1.69 ATS margin. The market overweights the headline portal losses while ignoring that the team's core returners are intact.

---

## Statistical Significance

| Test | Statistic | p-value |
|------|:---------:|:-------:|
| NEGATIVE_SHOCK vs MIDDLE (t-test on ATS margin) | t = 2.344 | **p = 0.019** |
| POSITIVE_SHOCK vs MIDDLE (t-test on ATS margin) | t = 1.139 | p = 0.255 |
| NEGATIVE_SHOCK ATS vs 50% (binomial) | 355/665 | p = 0.088 |
| HIGH_TURNOVER ATS vs 50% (binomial) | 328/609 | p = 0.062 |
| NEGATIVE_SHOCK as favorite vs 50% (binomial) | 226/409 | **p = 0.038** |
| Cohen's h (NEGATIVE_SHOCK vs 50%) | 0.068 | Small effect |

The t-test of NEGATIVE_SHOCK margin vs MIDDLE is significant at p < 0.02. The binomial test of the overall cover rate is marginal (p = 0.088), but the subset of NEGATIVE_SHOCK favorites reaches p = 0.038. Effect size is small (Cohen's h = 0.068).

---

## Phase 7 — Practical Assessment

### Signal characterization
- **What:** Teams with large net portal talent losses (NEGATIVE_SHOCK) cover early-season spreads at 53.4%, concentrated in Weeks 1-4, especially when favored (55.3%).
- **Why (hypothesis):** Market overreacts to headline portal departures. Bettors see "Team X lost 5 players to the portal" and shade lines, but returning core production + coaching continuity means the on-field product doesn't decline as much as expected.
- **Fade curve:** Effect is real and fades by Week 5. By mid-season the market corrects (cover rate drops to ~48%).

### Strengths
1. Directionally consistent across all 4 seasons (2022-2025)
2. Survives home/away, P5/G5, and most spread band controls
3. Significant t-test vs middle bucket (p = 0.019)
4. Clear fade curve — textbook early-season market inefficiency pattern
5. Strongest when combined with high returning production (intuitive mechanism)

### Weaknesses
1. Effect size is small (3.4pp over 50%, Cohen's h = 0.068)
2. Binomial test on raw cover rate is marginal (p = 0.088)
3. Not enough to overcome standard -110 vig on its own (need ~52.4% to break even)
4. 2023 season was weakest (51.7% cover)
5. Portal data quality improves over time — 2022 has more missing destinations

### Framing options
| Framing | Fit |
|---------|-----|
| Standalone model | No — effect too small for standalone wagering |
| Base engine feature | **Possible** — net_star_shock as a feature in a multivariate NCAAF model, specifically weighted for Weeks 1-4 |
| Badge/overlay | **Best fit** — "Portal Loss Overcorrection" badge on NCAAF spreads Weeks 1-4, boosting confidence when other signals align |
| Close | Not warranted — signal is real if modest |

---

## Decision: NEAR MISS

**Rationale:** The NEGATIVE_SHOCK early-season ATS edge is directionally real, consistent across seasons, and shows the expected fade curve. However:
- The raw effect (53.4% ATS) is below the threshold needed to be profitable after vig as a standalone signal
- Statistical significance is borderline at the aggregate level (p = 0.088 binomial), though the t-test vs middle bucket is clean (p = 0.019)
- The strongest subset (NEGATIVE_SHOCK favorites, 55.3%, p = 0.038) is promising but sample is moderate (409 games over 4 years)

**Recommended path forward:**
1. If/when building an NCAAF spread model, include `net_star_shock` as a Week 1-4 feature candidate — the t-test evidence justifies inclusion in a multivariate screen
2. The "Portal Loss Overcorrection" pattern is a legitimate badge for manual handicapping in early September
3. Do NOT build a standalone wagering system around this signal alone
4. Monitor 2026 season (Week 1 data available late August) to see if the pattern holds as portal volume continues to grow
5. The composite finding (NEGATIVE_SHOCK + HIGH_RETURN = 54.4%) suggests that adding returning production data strengthens the signal and could push it past the vig threshold in a proper model

---

## Data Artifacts

All analysis used CFBD API data pulled 2026-04-08. No files were modified in the repo. Key cached parquets used:
- `research/ncaaf/cfbd_games.parquet` (2022-2024 games)
- `research/ncaaf/cfbd_betting_lines.parquet` (2022-2024 lines)
- CFBD API live pulls: `/player/portal` (2022-2025), `/player/returning` (2022-2025), `/games` and `/lines` (2025)
