#!/usr/bin/env python3
"""
test_props.py — End-to-end test of the player props projection pipeline.

Fetches today's MIL @ CLE game (game_pk 831791), builds all required inputs,
and prints the full get_game_props() output as formatted JSON.

Usage:
    python3 test_props.py
"""

import json
import os
import sys

# ── 1. Schedule ───────────────────────────────────────────────────────────────

print("=" * 60)
print("STEP 1: Fetching today's schedule ...")
print("=" * 60)

from modules.schedule import fetch_schedule

TARGET_GAME_PK = 831791
TARGET_AWAY    = "MIL"
TARGET_HOME    = "CLE"
GAME_DATE      = "2026-03-12"

games = fetch_schedule(GAME_DATE)
print(f"  Found {len(games)} games for {GAME_DATE}")

game = next(
    (g for g in games if g.get("game_pk") == TARGET_GAME_PK),
    None,
)
if game is None:
    # Fallback: match by teams
    game = next(
        (g for g in games
         if g.get("away_team") == TARGET_AWAY and g.get("home_team") == TARGET_HOME),
        None,
    )

if game is None:
    print(f"\n  WARNING: {TARGET_AWAY} @ {TARGET_HOME} (pk={TARGET_GAME_PK}) "
          f"not found in today's schedule.")
    print("  Building a stub game dict for testing ...")
    game = {
        "game_pk":    TARGET_GAME_PK,
        "game_date":  GAME_DATE,
        "home_team":  TARGET_HOME,
        "away_team":  TARGET_AWAY,
        "game_time":  "7:10 PM ET",
        "game_time_et": "7:10 PM",
        "venue_name": "Progressive Field",
        "home_team_id": 114,
        "away_team_id": 158,
        "home_probable_pitcher": {"name": "TBD", "id": None},
        "away_probable_pitcher": {"name": "TBD", "id": None},
        "home_umpire": None,
    }
else:
    print(f"  ✓ Found: {game['away_team']} @ {game['home_team']}  "
          f"pk={game['game_pk']}  time={game.get('game_time','?')}")
    home_sp = game.get("home_probable_pitcher", {}).get("name") or "TBD"
    away_sp = game.get("away_probable_pitcher", {}).get("name") or "TBD"
    print(f"    Home SP: {home_sp}")
    print(f"    Away SP: {away_sp}")
    print(f"    Umpire:  {game.get('home_umpire') or 'unknown'}")

# ── 2. Pitcher K DB ───────────────────────────────────────────────────────────

print()
print("=" * 60)
print("STEP 2: Building pitcher K database ...")
print("=" * 60)

from modules.props_data import build_pitcher_k_db, build_batter_props_db

pitcher_k_db = build_pitcher_k_db()
print(f"  ✓ {len(pitcher_k_db)} pitchers loaded")

# Show CLE and MIL starters if known
home_sp_name = game.get("home_probable_pitcher", {}).get("name") or ""
away_sp_name = game.get("away_probable_pitcher", {}).get("name") or ""

for sp_name, label in [(home_sp_name, TARGET_HOME), (away_sp_name, TARGET_AWAY)]:
    if sp_name and sp_name != "TBD":
        profile = pitcher_k_db.get(sp_name.lower())
        if profile:
            print(f"  {label} SP ({sp_name}): "
                  f"K/9={profile.get('k_per_9', 0):.1f}  "
                  f"SwStr={profile.get('swstr_pct', 0):.3f}  "
                  f"IP/start={profile.get('avg_ip_per_start', 0):.1f}  "
                  f"GB%={profile.get('gb_pct', 0):.3f}")
        else:
            print(f"  {label} SP ({sp_name}): not found in DB")

# ── 3. Batter props DB ────────────────────────────────────────────────────────

print()
print("=" * 60)
print("STEP 3: Building batter props database ...")
print("=" * 60)

batter_props_db = build_batter_props_db()
print(f"  ✓ {len(batter_props_db)} batters loaded")

from modules.props_data import get_team_top_batters, get_team_k_rate

for team in (TARGET_HOME, TARGET_AWAY):
    top = get_team_top_batters(team, batter_props_db, n=3)
    k_rate = get_team_k_rate(team, batter_props_db)
    print(f"\n  {team} top batters (K-rate: {k_rate:.3f}):")
    for b in top:
        print(f"    {b['name']:<22}  xSLG={b.get('xslg') or b.get('slg', 0):.3f}  "
              f"barrel={b.get('barrel_pct') or 0:.3f}  "
              f"hard={b.get('hard_pct') or 0:.3f}")
    if not top:
        print(f"    (no batters found for {team})")

# ── 4. Props lines (DraftKings / Odds API) ────────────────────────────────────

print()
print("=" * 60)
print("STEP 4: Fetching props lines ...")
print("=" * 60)

from modules.props_odds import fetch_props_lines

odds_api_key = os.environ.get("ODDS_API_KEY") or ""
if odds_api_key:
    print(f"  ODDS_API_KEY found ({odds_api_key[:8]}...)")
else:
    print("  ODDS_API_KEY not set — will try DraftKings only")

props_lines = fetch_props_lines(
    home_team    = TARGET_HOME,
    away_team    = TARGET_AWAY,
    game_date    = GAME_DATE,
    odds_api_key = odds_api_key or None,
)

if props_lines:
    print(f"  ✓ Lines found for {len(props_lines)} players:")
    for player, lines in list(props_lines.items())[:10]:
        k_str  = f"K={lines['k']:.1f}"  if lines.get("k")  is not None else ""
        tb_str = f"TB={lines['tb']:.1f}" if lines.get("tb") is not None else ""
        parts  = [s for s in (k_str, tb_str) if s]
        if parts:
            print(f"    {player:<28}  {' · '.join(parts)}")
    if len(props_lines) > 10:
        print(f"    ... and {len(props_lines) - 10} more")
else:
    print("  No lines returned (DK may not have this game yet, or API is unavailable)")
    print("  Props projections will still be calculated — lines will show as None")

# ── 5. Umpire ─────────────────────────────────────────────────────────────────

print()
print("=" * 60)
print("STEP 5: Getting umpire rating ...")
print("=" * 60)

from modules.umpires import get_umpire_rating

umpire_name = game.get("home_umpire")
umpire      = get_umpire_rating(umpire_name)
print(f"  Umpire: {umpire_name or 'unknown'}")
print(f"  k_factor={umpire.get('k_factor', 1.0):.3f}  "
      f"runs_factor={umpire.get('runs_factor', 1.0):.3f}")

# ── 6. Weather / factors ──────────────────────────────────────────────────────

print()
print("=" * 60)
print("STEP 6: Fetching weather for factors dict ...")
print("=" * 60)

from modules.weather import fetch_weather

weather = fetch_weather(TARGET_HOME, game_time_et=game.get("game_time"))
print(f"  temp={weather.get('temperature_f', '?')}°F  "
      f"wind={weather.get('wind_speed_mph', 0):.0f}mph "
      f"{weather.get('wind_desc', '')}  "
      f"dome={weather.get('is_dome', False)}")

# Build a minimal factors dict (mirrors what project_game() returns)
from config import STADIUMS
stadium    = STADIUMS.get(TARGET_HOME, {})
park_raw   = stadium.get("park_factor", 100)
park_factor = park_raw / 100.0

factors = {
    "park_factor":        park_factor,
    "wind_desc":          weather.get("wind_desc", ""),
    "wind_speed":         weather.get("wind_speed_mph", 0),
    "wind_speed_mph":     weather.get("wind_speed_mph", 0),
    "wind_direction":     weather.get("wind_direction"),
    "temperature_f":      weather.get("temperature_f"),
    "umpire_name":        umpire_name,
    "umpire_runs_factor": umpire.get("runs_factor", 1.0),
}
print(f"  park_factor={park_factor:.3f}  (raw={park_raw})")

# ── 7. get_game_props() ───────────────────────────────────────────────────────

print()
print("=" * 60)
print("STEP 7: Calling get_game_props() ...")
print("=" * 60)

from modules.props_projections import get_game_props

props = get_game_props(
    game         = game,
    home_sp_name = home_sp_name,
    away_sp_name = away_sp_name,
    factors      = factors,
    umpire       = umpire,
    pitcher_k_db = pitcher_k_db,
    batter_db    = batter_props_db,
    props_lines  = props_lines,
)

print(f"  ✓ {len(props)} props generated")
print()

# ── 8. Print results ──────────────────────────────────────────────────────────

print("=" * 60)
print("RESULTS")
print("=" * 60)
print()

plays    = [p for p in props if p.get("is_play")]
no_plays = [p for p in props if not p.get("is_play")]

if plays:
    print(f"  PLAYS ({len(plays)}):")
    for p in plays:
        edge_pct = p.get("edge_pct") or 0
        sign     = "+" if p.get("lean") == "OVER" else "-"
        print(f"    [{p['market']}] {p['player_name']:<24}  "
              f"proj={p['projection']:.2f}  "
              f"line={p['line'] if p.get('line') is not None else '—'}  "
              f"edge={sign}{edge_pct*100:.1f}%  {p.get('lean','')}")
    print()

if no_plays:
    print(f"  NO PLAYS ({len(no_plays)}):")
    for p in no_plays:
        edge_pct = p.get("edge_pct")
        edge_str = f"{edge_pct*100:.1f}%" if edge_pct is not None else "no line"
        print(f"    [{p['market']}] {p['player_name']:<24}  "
              f"proj={p['projection']:.2f}  "
              f"line={p['line'] if p.get('line') is not None else '—'}  "
              f"edge={edge_str}")
    print()

print("=" * 60)
print("FULL JSON OUTPUT")
print("=" * 60)
print(json.dumps(props, indent=2))
