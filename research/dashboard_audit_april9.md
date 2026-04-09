# Dashboard Audit — April 9, 2026

Audited: `/root/mlb-model/dashboard.py` (6,774 lines)
VM: `root@142.93.242.4`
Date of audit: 2026-04-09

---

## Summary Table

| Sport | Data File | Cards Today | Bugs | Inconsistencies |
|-------|-----------|-------------|------|-----------------|
| MLB | `results.json` + 6 signal JSONs | 6 no-plays, 0 plays | `_sim_sigs` NameError; `open_line` never set | TT pills invisible on no-play cards |
| NHL | `nhl_results.json` | 10 signals shown as plays | All tiers=MEDIUM; open_total injection broken | `nhl_decisions.parquet` has HIGH/SHADOW_MEDIUM; JSON has only MEDIUM |
| NBA | `nba_results.json` | 0 plays, 6 no-plays | `_nba.get()` NameError in overlay block | open_total injection broken (full name vs abbrev) |
| Soccer | `soccer_results.json` | 0 signals (no match day) | None | source=stale; no signals expected |
| Golf | `golf_results.json` | 66 plays (leans+candidates) | Matchup book shows `datagolf_model` | G15 kill_switch=True suppresses all G15 |

---

## MLB Game Cards

### Data Flow

- **Primary data file**: `results.json` (pushed from local machine)
  - Keys: `generated_at`, `game_date`, `plays`, `no_plays`, `parlay`, `parlay_3`, `parlay_5`, `parlay_7`, `season_record`, `transactions`, `mlb_clv_summary`, `stop_rule_status`, `daily_review`
  - Today (2026-04-09): 0 plays, 6 no-play games

- **Signal enrichment** (loaded in `_load_json_signals()`):
  - `mlb_sim/logs/signals_2026.json` — V1 full game UNDER signals (54 total, 0 today)
  - `mlb_sim/logs/f5_signals_2026.json` — F5 total signals (53 total, 0 today)
  - `mlb_sim/logs/f5_runline_2026.json` — F5 run line signals (3 total, 0 today)

- **Shadow modifier data**:
  - `mlb_sim/logs/team_total_shadow_2026.json` — Team total under/over flags
  - `mlb_sim/logs/cs013_shadow_2026.json` — CS013 bullpen deterioration (6 today, all false)
  - `mlb_sim/logs/shadow_signals_2026.json` — ST02/other shadow signals (24 today, all false)
  - `mlb_sim/logs/cs028_shadow_2026.json` — CS028 Bayesian blowup (1 fires today)
  - `mlb_sim/logs/kp04_shadow_2026.json` — KP04 K-prop shadow (11 today)

### Primary Join Key

- `results.json` game cards join to signal logs via `away_team@home_team` string key (e.g. `"OAK@NYY"`)
- Team Total flags join via `str(game_pk)` — stored as string keys in `_load_shadow_flags()`
- `_shadow_badge_html()` receives `game.get("game_pk")` as an INT; cs013/st02 flags use INT keys

### Card Routing Logic (`_render_mlb_tab`)

1. Games with live signals → `play_cards` (green border `#22c55e`, shown expanded)
2. Games with only shadow-only V1 signals → `shadow_cards` (red border `#ef4444`, labeled "SHADOW MONITORING")
3. Games with no signals → `noplay_cards` (grey border `#374151`, collapsed in expander "All Other Games Today")

### Border Color Logic (`_render_card`)

- Play card: `#22c55e` (green) by default
- Play card with voided scratch: `#dc2626` (red)
- Play card with partial signal only: `#ef4444` (light red)
- No-play card with partial: `#ef4444`
- No-play card clean: `#374151` (grey)

### Pills Shown (play cards only)

- **Green modifier pills**: S12 (overlay active), P09 (overlay active)
- **Yellow modifier pills**: CS013, CS028, KP04, ST02 (shadow monitors)
- **Blue pills**: TT↓H, TT↓A (team total under), TT↑H (team total over) with posted total and gap

### What's Working

- All 6 data files for signal enrichment exist and load correctly
- TT flag join is correct in `_render_card` (uses `str(game_pk)` which matches TT log's string keys)
- Shadow badge logic (`_shadow_badge_html`) uses int key matching cs013/st02's int keys — correct
- Engine status panel (green/yellow pills) renders from 5 status JSON files
- Stop rule suspension banner reads from `results.json.stop_rule_status`
- Yesterday's results block reads correctly from V1/F5/RL JSON logs
- HR line override system (load/display/edit) is functional

### What's Broken

**BUG 1: `_sim_sigs` NameError — "Recent Sim Signals" expander never renders**

At line 3993 in `dashboard.py`, the code does:
```python
if os.path.exists(_sim_signals_path):
    _resolved = _sim_sigs[_sim_sigs["resolved"].isin([1, 2])]...
```
`_sim_sigs` is never assigned. The variable `_sim_signals_path` points to `mlb_sim/logs/signals_2026.parquet` which **does exist** (32,483 bytes). Every page render reaches this code, hits a `NameError`, and is silently swallowed by the surrounding `try/except pass`. The "Recent Sim Signals" expander is permanently broken.

Fix: add `_sim_sigs = pd.read_parquet(_sim_signals_path)` before the `if os.path.exists(...)` check, or move the path check to guard the load.

**BUG 2: `open_line` never populated in MLB signals → line movement arrows never show**

In `_load_json_signals()`, `_info["open_line"] = _r.get("open_line")` is set from the signal JSON. However, `open_line` is `None` for all 54 signals in `signals_2026.json`. The `_line_movement_html()` function returns `""` when `open_total is None`. Line movement arrows (↑/↓) never appear on MLB play cards.

Root cause: the MLB signal pipeline does not write `open_line` to the signal log. The field exists in the schema but is never populated.

### What's Inconsistent

**INCONSISTENCY 1: TT pills invisible on no-play games**

Today has 4 games with active Team Total signals (OAK@NYY, DET@MIN, ARI@NYM, CHW@KCR). All 6 games today are no-plays (no V1/F5/RL signals). TT pills are only rendered inside the `if signals:` branch of `_render_card`. The `else` (no-play) branch has no TT pill rendering. The TT shadow monitor fires on these games but the information is invisible on the dashboard.

**KEY TYPE SPLIT in `_load_shadow_flags`**: cs013/st02/kp04/cs028 signals use INT keys (from `game_id` field in signal logs). TT flags use STR keys (from `str(game_pk)` in TT log). This creates two separate dict entries for the same game — e.g. key `823565` (int) and `'823565'` (str) both exist. `_render_card` looks up with str key (gets TT flags) while `_shadow_badge_html` looks up with int key (gets cs013/st02 flags). This is internally consistent today but fragile: if a game has both cs013=True and TT signals, `_render_card`'s str-keyed lookup would miss the cs013 flag (it's in the int-keyed entry). Today all cs013/st02 flags are False so no visible impact, but the split is a latent data alignment bug.

---

## NHL Game Cards

### Data Flow

- **Primary data file**: `nhl_results.json`
  - Keys: `generated_at`, `last_updated`, `pipeline_run_date`, `signals_source`, `game_date`, `today_signals`, `recent_results`, `season_performance`, `ot_diagnostics`, `clv_summary`, `data_quality_warning`, `daily_review`
  - Today: 10 signals, all with `confidence_tier = "MEDIUM"`

- **Supplementary**: `nhl/nhl_decisions.parquet`
  - Today: same 10 games, tiers split as 4 HIGH + 6 SHADOW_MEDIUM

- **Open total injection**: `nhl/data/nhl_lines_open_2026_04_09.json`
  - Contains 1 game (SJS@EDM), but uses full team names

### Primary Join Key

- Signals matched by `(home_team, away_team)` tuple for open_total injection

### Card Routing Logic (`_render_nhl_tab`)

- `plays = [s for s in today_signals if s.get("confidence_tier") in ("HIGH", "MEDIUM")]`
- `no_plays = remaining signals`
- Section header counts all 10 as plays (all are MEDIUM)
- No_plays section (low confidence) is a collapsed expander — empty today

### Border Color Logic (`_render_nhl_signal_card`)

```python
is_shadow = tier.startswith("SHADOW_")   # only true for "SHADOW_MEDIUM", "SHADOW_HIGH" etc
is_play   = tier == "HIGH"               # only true for "HIGH"
_border   = "#22c55e" if is_play else ("#dc2626" if is_shadow else "#374151")
```

- HIGH → green border, star3 CSS class (3-star play card)
- SHADOW_* → red border, noplay CSS class
- MEDIUM/LOW/anything else → grey border, noplay CSS class

### Pills Shown

- Side badge (OVER/UNDER)
- Confidence badge with stake units
- Goalie TBD badge (warning yellow) when goalie unconfirmed
- SHADOW label badge for SHADOW_* tiers
- Goalie status row (confirmed/backup/back-to-back)
- Caution banner for 6.5-line OVER games

### What's Working

- Signal card layout renders correctly for all tiers
- Goalie status fields are populated (`goalie_confirmed_home: False` today — TBD badge shows)
- `nhl_results.json` file exists and loads cleanly
- `stake_units` field is set (0.75 for MEDIUM)
- Recent results table renders when data available
- Season performance tabs (validate/OOS/combined) render

### What's Broken

**BUG 3: All NHL signals in `nhl_results.json` have `confidence_tier = "MEDIUM"` — HIGH and SHADOW_MEDIUM tiers are lost**

`nhl_decisions.parquet` for today shows: 4 games at HIGH tier, 6 games at SHADOW_MEDIUM. The JSON published to the dashboard collapses all to MEDIUM. As a result:

- `is_play = tier == "HIGH"` is always `False` for all 10 signals
- All 10 game cards render with grey border (`#374151`) and `noplay` CSS class — no star rating
- The section header says "10 signals" suggesting plays, but the cards look like no-plays
- SHADOW_MEDIUM signals should show red border + "SHADOW" badge but don't

This is a pipeline issue: `push_nhl.py` (or whatever writes `nhl_results.json`) is not preserving the HIGH/SHADOW_MEDIUM distinction from the parquet.

**BUG 4: NHL `open_total` injection always fails — team name format mismatch**

In `_render_nhl_tab`, the injection code builds `_nhl_open_map` keyed by `(home_team, away_team)` tuples from the open lines JSON. The open lines JSON uses full names ("San Jose Sharks", "Edmonton Oilers"). The `nhl_results.json` signals use abbreviations ("SJS", "ANA", "TOR"). Every lookup returns `None`. The line movement function receives `open_total=None` and returns empty string. NHL line movement arrows never appear.

### What's Inconsistent

- `nhl_decisions.parquet` has `confidence_tier` values of HIGH/SHADOW_MEDIUM, but `nhl_results.json` only has MEDIUM. The dashboard reads `nhl_results.json` not the parquet. The parquet is never read by the dashboard for today's signals.
- `stake_units = 0.75` hardcoded for all MEDIUM signals, which is correct per the `{"HIGH": 1.0, "MEDIUM": 0.75}` default map, but the HIGH signals are not getting their 1.0u sizing.

---

## NBA Game Cards

### Data Flow

- **Primary data file**: `nba_results.json`
  - Keys: `generated_at`, `game_date`, `is_playoff_day`, `plays`, `no_plays`, `season_accuracy`, `recent_results`, `ot_diagnostics`, `playoff_performance`, `clv_summary`, `signal_tracking`, `stop_rule_status`, `daily_review`
  - Today: 0 plays, 6 no-plays (5 with `bet_tier=None/NA`, 1 with `bet_tier="CONTEXT"`)

- **Open total injection**: `nba/data/nba_lines_open_2026_04_09.json` (exists)

- **Supporting files**: `nba/data/high_line_under_shadow.csv` (35 rows), `nba/config_segment_overlay.json` (`overlay_active=True`)

### Primary Join Key

- Open total injection keyed by `(home_team, away_team)` tuple

### Card Routing Logic (`_render_nba_tab`)

- `plays = nba.get("plays", [])` — today: 0 games
- `no_plays = nba.get("no_plays", [])` — today: 6 games (collapsed in "No Plays — 6 games" expander)
- Signal board section: `tier1a/tier1b/tier2/context/conflicts` filtered from `plays + no_plays`
  - Today: 1 CONTEXT game (LAL@GSW), no TIER_* games

### Border Color / Tier Logic (`_render_nba_card`)

```python
is_play = bet_tier in ("TIER_1A", "TIER_1B", "TIER_2", "P1", "P2", "P4", "REF_UNDER")
conf_star = {"TIER_1A": "star3", "TIER_1B": "star3", "TIER_2": "star2",
             "P1": "star3", "P2": "star2", "P4": "star2",
             "REF_UNDER": "star2"}.get(bet_tier, "noplay")
```

CONTEXT is not in `is_play` set → noplay grey styling. The `_nba_tier_badge("CONTEXT")` renders a grey badge with "CONTEXT · 0u".

### Pills / Signal Display

- Tier badge (CORE, TIER 1B, TIER 2, CONTEXT, P1, P2, P4)
- Lean badge (OVER/UNDER)
- Line with movement arrow (when `open_total` injected)
- Signal fires list (Venue, Shot, OREB, Pace)
- Playoff context block (round, game number, series standing)
- Archetype signal badge (purple)
- Shot profile signal badge
- Injury warnings (away/home)
- OT diagnostics section

### What's Working

- Card rendering logic is comprehensive and clean for play cards
- Matchup signal board (tier1a/tier1b/tier2/context) correctly categorizes all games
- Stop rule suspension banners work
- `signal_tracking` panel (season W-L by tier) renders when data present
- PLO parlay boards (P1/P2/P4) correctly suppressed when `is_playoff_day=False`
- Recent results table renders
- CLV section renders when `clv_summary` populated

### What's Broken

**BUG 5: `_nba.get("game_date")` NameError — today's high-line shadow tracking silently fails**

Inside `_render_nba_tab`, within the segment overlay block (`overlay_active=True`), there is:
```python
_today_str = _nba.get("game_date", "")
```
The variable `_nba` is not defined anywhere in `_render_nba_tab`. The correct variable is `nba` (the result of `load_nba_results()`). `_nba` is only defined much later, inside `_render_tracker_tab` as a parquet dataframe. Because `overlay_active=True` today and `high_line_under_shadow.csv` exists, this code path is reached on every render. The `NameError` is swallowed by `try/except pass`. Two things fail silently:
1. Today's tagged high-line UNDER shadow games are not shown
2. Season summary stats for the high-line shadow never display

Fix: replace `_nba.get("game_date", "")` with `nba.get("game_date", "")`.

**BUG 6: NBA `open_total` injection always fails — team name format mismatch**

Same issue as NHL: `nba/data/nba_lines_open_2026_04_09.json` uses full team names ("San Antonio Spurs", "Denver Nuggets"), while `nba_results.json` games use three-letter abbreviations ("TOR", "MIA", "BKN"). Every lookup in the `_nba_open_map` returns `None`. `open_total` is never set for any NBA game. Line movement arrows never appear.

### What's Inconsistent

- `nba_phase6_po_shadow.parquet` is referenced in the segment overlay block but does not exist at `/root/mlb-model/nba/data/nba_phase6_po_shadow.parquet`. The `if os.path.exists()` guard prevents a crash, but the PO shadow stats never render.
- The NBA tab has two structural sections that both show games: the main "Plays" block (uses `nba.get("plays")`) and the "Matchup Signal Board" (re-filters `plays + no_plays`). Today the Matchup Signal Board correctly shows LAL@GSW as CONTEXT only, while the main section shows nothing (0 plays). These are redundant but consistent today.

---

## Soccer Game Cards

### Data Flow

- **Primary data file**: `soccer_results.json`
  - Keys: `generated_at`, `last_updated`, `pipeline_run_date`, `signals_source`, `game_date`, `deployment_start_date`, `model_description`, `active_scope_note`, `today_signals`, `recent_results`, `season_performance`, `data_quality_warning`, `league_deployment`, `parlay_candidates`, `suggested_parlay`, `daily_review`
  - Today: 0 `today_signals`, 0 `recent_results`, 0 `parlay_candidates`, `signals_source = "stale"`

### Primary Join Key

- No join — signals are self-contained in `soccer_results.json`

### Card Routing Logic (`_render_soccer_tab`)

- `plays = [s for s in today_signals if s.get("confidence_tier") in ("HIGH", "MEDIUM")]`
- `low_sigs = remaining signals`
- Today: no signals → "No qualified Over 2.5 signals today" caption

### Border Color Logic (`_render_soccer_signal_card`)

- HIGH → star3 CSS class (`.game-card.star3` = green left border)
- MEDIUM → star2 CSS class (`.game-card.star2` = yellow left border)
- Other → noplay CSS class

No explicit border color override inline (uses CSS class-driven `.game-card` rules).

### Pills Shown

- OVER 2.5 badge (green)
- League label
- Matchup
- Confidence tier badge
- Stats row: Line (always 2.5), Edge pp, Model Goals, Over Price (if set), Kickoff
- Market move badge
- Lineup confirmed/estimated

### What's Working

- File loads and parses correctly
- Active scope note banner (Bundesliga MEDIUM only) renders
- League deployment status block renders
- Over 1.5 parlay section renders (no candidates today = "No parlay candidates today" message)
- Season performance section renders when `overall.n > 0`

### What's Broken / Inconsistent

- `signals_source = "stale"` shows an amber "stale" source badge today. This is correct behavior — no new soccer data (no match day Wednesday April 9 for active leagues in scope).
- No functional bugs observed. The empty state is handled gracefully.
- The `active_scope_note` restricts to "Bundesliga MEDIUM tier only" — this is displayed correctly.

---

## Golf Game Cards

### Data Flow

- **Primary data file**: `golf_results.json`
  - Keys: `generated_at`, `sport`, `event_name`, `event_id`, `is_major`, `last_updated`, `n_candidates`, `n_leans`, `plays`, `season_stats`, `recent_results`, `matchup_candidates`, `matchup_n_candidates`, `matchup_n_leans`, `g13_signals`, `g13_avoids`, `g13_status`, `g14_signals`, `g14_win_watchlist`, `g14_field_type`, `g14_kill_switch`, `g14_status`, `g15_signals`, `g15_elite_density_bucket`, `g15_kill_switch`, `g15_status`, `model_info`
  - Today: Masters Tournament, 66 plays (46 leans + 20 candidates), 1 G13 signal, 0 G14, 0 G15

- **Golf shadow log**: `golf/shadow/golf_shadow_log.parquet` (referenced for G13×S6 and CL03 shadow counts)

### Primary Join Key

- No join — `plays` array is self-contained from push script

### Card Routing Logic (Outright Board tab)

- `plays` filtered to remove: (a) under + odds < -200, (b) missing `market_prob`
- Split by `market` field into sub-tabs: Make Cut, Top 20, Top 10, Top 5, Winner
- Within each market: leans shown always; candidates in collapsed expander
- Sort: over first, then under; leans before candidates; by edge descending

### Border Color / Styling

- **Outright board**: No `game-card` class used. Cards are plain `div` rows (table-like layout) with `border-bottom: 1px solid #1e2d4a`. No play/noplay color distinction — all rows look the same regardless of classification.
- **Matchup tab**: Plain `div` rows with `border-bottom: 1px solid #eee` (light grey — day-mode only; invisible in dark mode).
- **G13/G14/G15 tabs**: Similar inline row layouts with `border-bottom: 1px solid #1e2d4a`.

### Pills / Badges Shown

- Outright board: classification badge (lean=yellow `#f1c40f`, candidate=green `#2ecc71`), inline stats (model%, book%, edge, direction, odds)
- Matchup tab: classification badge (candidate=green, lean=yellow), match type, book, edge
- G13 tab: "G13 WAVE" green badge, draw quintile, DG cut prob, adj cut prob, odds, edge

### What's Working

- Masters Tournament data loaded correctly with 66 plays
- Market sub-tabs render correctly (Make Cut, Top 20, Top 10, Top 5, Winner)
- G13 signal (1 today) renders correctly in G13 tab
- G14 status "LIVE_SHADOW" shows; no signals today (correct)
- Season stats and recent results sections structured correctly
- `golf_shadow_log.parquet` is read for G13×S6 and CL03 shadow counts

### What's Broken / Inconsistent

**INCONSISTENCY 2: Golf matchup `book` field shows "datagolf_model" — not a real book**

All 20 matchup candidates have `book = "datagolf_model"`. The matchup card renders this as the book name. The caption below clarifies "Soft book tracking: building sample for Bovada/Bet365 hypothesis test", but the rendered "datagolf_model" label looks like a mistake to a reader unfamiliar with the context.

**INCONSISTENCY 3: G15 kill switch suppresses content silently**

`g15_kill_switch = True` causes a red banner "G15 signals suppressed this week — anomaly detected" to render, but `g15_elite_density_bucket` and signal list are not shown. If G15 was expected to be active this week (Masters is a major), the suppression may be unintentional.

**INCONSISTENCY 4: Matchup row border is `#eee` (white/light grey)**

The matchup tab uses `border-bottom: 1px solid #eee`. The entire rest of the dashboard uses dark mode colors (`#1e2d4a`, `#374151`). The `#eee` border is invisible in dark mode, making matchup rows appear borderless.

---

## Cross-Cutting Issues

### 1. `open_total` injection broken for NHL and NBA (same root cause)

Both `_render_nhl_tab` and `_render_nba_tab` inject `open_total` into signal/game dicts before rendering cards by matching `(home_team, away_team)` tuples. The open lines JSON files use full team names ("San Jose Sharks", "Toronto Maple Leafs", "Denver Nuggets") while the results JSON files use 3-letter abbreviations ("SJS", "TOR", "DEN"). Every lookup returns `None`. `_line_movement_html()` is called with `open_total=None` and returns `""`. **Line movement arrows (↑/↓) never appear for NHL or NBA.**

MLB is unaffected by this specific bug because it reads `open_line` from the signal log directly (not from a snapshot file), but that field is also `None` for all 54 current signals — so MLB line movement arrows also never show.

In total, line movement is non-functional for all three sports.

### 2. Silent error handling masks bugs

Large blocks of rendering logic for MLB, NBA, and NHL are wrapped in `try/except pass`. At least 3 confirmed bugs produce exceptions that are silently swallowed:
- `_sim_sigs` NameError (MLB, line ~3993)
- `_nba` NameError (NBA, line ~3178)
- `open_total` injection team-name mismatch (NHL, NBA — KeyError/None returns silently ignored)

The `try/except pass` pattern is used to prevent dashboard crashes, but it also makes bugs invisible during normal operation.

### 3. Pipeline freshness stamps

`shared/last_updated.json` is fully populated with timestamps for all sports:
- `mlb_confirm`: 2026-04-09T13:03:05Z (fresh)
- `nhl`: 2026-04-09T16:02:46Z (fresh)
- `nba`: 2026-04-09T14:00:12Z (fresh)
- `soccer`: 2026-04-09T14:00:04Z (fresh)
- `golf`: 2026-04-09T12:00:37Z (fresh)

All within 26-hour staleness threshold. The `_pipeline_freshness()` function will show green "📊 Last updated" banners for all sports.

### 4. No-play card information density

No-play cards (for MLB, NHL collapsed section, NBA collapsed section) show minimal context: matchup, time, weather, proj total, line, and a one-line reason. Shadow signals (TT flags, CS013, etc.) are not shown on no-play cards. A user cannot see Team Total shadow signals for games without a primary V1/F5 signal.

---

## File Reference

| File | Purpose | Sport |
|------|---------|-------|
| `/root/mlb-model/results.json` | MLB game projections + plays | MLB |
| `/root/mlb-model/nba_results.json` | NBA game projections + plays | NBA |
| `/root/mlb-model/nhl_results.json` | NHL signals | NHL |
| `/root/mlb-model/soccer_results.json` | Soccer Over 2.5 signals | Soccer |
| `/root/mlb-model/golf_results.json` | Golf outright + matchup signals | Golf |
| `/root/mlb-model/mlb_sim/logs/signals_2026.json` | V1 full game UNDER signals | MLB |
| `/root/mlb-model/mlb_sim/logs/f5_signals_2026.json` | F5 total signals | MLB |
| `/root/mlb-model/mlb_sim/logs/f5_runline_2026.json` | F5 run line signals | MLB |
| `/root/mlb-model/mlb_sim/logs/team_total_shadow_2026.json` | Team total flags | MLB |
| `/root/mlb-model/mlb_sim/logs/cs013_shadow_2026.json` | Bullpen deterioration shadow | MLB |
| `/root/mlb-model/mlb_sim/logs/shadow_signals_2026.json` | ST02/other shadow signals | MLB |
| `/root/mlb-model/mlb_sim/logs/cs028_shadow_2026.json` | Bayesian blowup shadow | MLB |
| `/root/mlb-model/mlb_sim/logs/kp04_shadow_2026.json` | K-prop shadow | MLB |
| `/root/mlb-model/mlb_sim/logs/signals_2026.parquet` | V1 signals (parquet, for expander) | MLB |
| `/root/mlb-model/nhl/nhl_decisions.parquet` | NHL signals with correct tiers | NHL |
| `/root/mlb-model/nba/data/high_line_under_shadow.csv` | High-line under shadow tracker | NBA |
| `/root/mlb-model/nba/config_segment_overlay.json` | NBA overlay config | NBA |
| `/root/mlb-model/shared/last_updated.json` | Pipeline freshness timestamps | All |

---

## Bug Priority Summary

| # | Sport | Bug | Severity | Fix |
|---|-------|-----|----------|-----|
| 1 | MLB | `_sim_sigs` NameError — "Recent Sim Signals" expander never renders | Medium | Add `_sim_sigs = pd.read_parquet(_sim_signals_path)` before use |
| 2 | MLB | `open_line = None` for all signals — line movement arrows never show | Low | MLB signal pipeline needs to write `open_line` field |
| 3 | NHL | All signals have `confidence_tier = "MEDIUM"` — HIGH/SHADOW_MEDIUM lost from JSON | High | Fix `push_nhl.py` to preserve HIGH/SHADOW_MEDIUM distinction |
| 4 | NHL | `open_total` injection fails (full team names vs abbreviations) | Low | Normalize team names or use consistent format in open lines snapshot |
| 5 | NBA | `_nba.get("game_date")` NameError — high-line shadow display broken | Medium | Replace `_nba.get(...)` with `nba.get(...)` (line ~3178) |
| 6 | NBA | `open_total` injection fails (full team names vs abbreviations) | Low | Same fix as NHL |
| 7 | MLB | TT pills invisible for games with no primary signal | Low | Add TT pill rendering to no-play card `else` branch |
| 8 | Golf | Matchup `border-bottom: #eee` invisible in dark mode | Cosmetic | Change to `#1e2d4a` to match rest of UI |
