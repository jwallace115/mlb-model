#!/usr/bin/env python3
"""
AI-generated daily and weekly results review.

Calls Claude API (claude-sonnet-4-5) to generate narrative reviews of
model performance for MLB, NBA, NHL, and Soccer.

Usage:
    from modules.ai_review import generate_daily_review, generate_weekly_review
    from modules.ai_review import build_graded_games

    graded = build_graded_games("mlb", "2026-03-17")
    review = generate_daily_review(graded, "mlb", "2026-03-17")
"""

import json
import os
import sys
from datetime import date, datetime, timedelta, timezone
from typing import Any

_REPO_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EXPLAIN_MISS_THRESHOLD = 8.0

# ── API client ─────────────────────────────────────────────────────────────────

def _get_api_key() -> str | None:
    """Check env var, then .env file."""
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key
    env_path = os.path.join(_REPO_DIR, ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("ANTHROPIC_API_KEY=") and "=" in line:
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val and not val.startswith("your_"):
                            return val
        except Exception:
            pass
    return None


def _get_client():
    try:
        import anthropic
        key = _get_api_key()
        if not key:
            return None
        return anthropic.Anthropic(api_key=key)
    except ImportError:
        return None


# ── Data extraction helpers ────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    try:
        return round(float(v), 2) if v is not None else None
    except (TypeError, ValueError):
        return None


def _build_mlb_graded(review_date: str) -> list[dict]:
    """Extract MLB graded plays for review_date from graded_results DB."""
    try:
        sys.path.insert(0, _REPO_DIR)
        import db
        db.init_db()
        rows = db.get_all_graded_results()
    except Exception as e:
        print(f"[ai_review] MLB DB read failed: {e}", file=sys.stderr)
        return []

    games = []
    for r in rows:
        if r.get("game_date") != review_date:
            continue
        if r.get("was_a_play") != 1:
            continue
        if r.get("result") not in ("WIN", "LOSS", "PUSH"):
            continue

        proj = _safe_float(r.get("projected_total"))
        actual = _safe_float(r.get("actual_total"))
        gap = round(actual - proj, 1) if actual is not None and proj is not None else None

        g: dict[str, Any] = {
            "game_date":        review_date,
            "home_team":        r.get("home_team", ""),
            "away_team":        r.get("away_team", ""),
            "signal_side":      r.get("recommendation", ""),
            "confidence_tier":  r.get("confidence", "LOW"),
            "decision_line":    _safe_float(r.get("line")),
            "model_projection": proj,
            "edge_at_decision": _safe_float(r.get("edge")),
            "actual_total":     actual,
            "result":           r.get("result"),
            "projection_gap":   gap,
            "clv_directional":  _safe_float(r.get("clv_directional")),
        }
        # Sport-specific features (omit nulls)
        for k, fk in [
            ("home_sp_xfip", "sp_home_xfip"), ("away_sp_xfip", "sp_away_xfip"),
            ("temperature", "temperature"), ("wind_speed", "wind_speed"),
            ("wind_direction", "wind_direction"), ("umpire_runs_factor", "umpire_rating"),
        ]:
            v = _safe_float(r.get(fk))
            if v is not None:
                g[k] = v
        if r.get("wind_desc"):
            g["wind_desc"] = r["wind_desc"]
        games.append(g)
    return games


def _load_nba_projections(review_date: str):
    """Load context features from nba_daily_projections.parquet, keyed by game_id."""
    proj_path = os.path.join(_REPO_DIR, "nba", "data", "nba_daily_projections.parquet")
    if not os.path.exists(proj_path):
        return {}
    try:
        import pandas as pd
        pdf = pd.read_parquet(proj_path)
        pdf = pdf[pdf["game_date"] == review_date]
        return {str(row["game_id"]): row for _, row in pdf.iterrows()}
    except Exception:
        return {}


def _build_nba_graded(review_date: str) -> list[dict]:
    """Extract NBA graded plays from nba_results_log.parquet for review_date."""
    path = os.path.join(_REPO_DIR, "nba", "data", "nba_results_log.parquet")
    if not os.path.exists(path):
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(path)
        df = df[
            (df["game_date"] == review_date) &
            (df["regulation_result"].isin(["WIN", "LOSS", "PUSH"]))
        ]
    except Exception as e:
        print(f"[ai_review] NBA parquet read failed: {e}", file=sys.stderr)
        return []

    # Load context features from daily projections
    proj_ctx = _load_nba_projections(review_date)

    games = []
    for _, r in df.iterrows():
        proj = _safe_float(r.get("pred_total"))
        actual = _safe_float(r.get("actual_total"))
        gap = round(actual - proj, 1) if actual is not None and proj is not None else None

        g: dict[str, Any] = {
            "game_date":        review_date,
            "home_team":        str(r.get("home_team", "")),
            "away_team":        str(r.get("away_team", "")),
            "signal_side":      str(r.get("lean", "")),
            "confidence_tier":  str(r.get("confidence", "LOW")),
            "decision_line":    _safe_float(r.get("line")),
            "model_projection": proj,
            "edge_at_decision": _safe_float(r.get("edge")),
            "actual_total":     actual,
            "result":           str(r.get("regulation_result", "")),
            "projection_gap":   gap,
            "was_playoff":      bool(r.get("is_playoff", False)),
            "clv_directional":  _safe_float(r.get("clv_directional")),
        }

        # OT flag from results log
        went_ot = r.get("went_to_ot")
        if went_ot is not None and float(went_ot) == 1:
            g["went_to_ot"] = True
            reg_total = _safe_float(r.get("regulation_total"))
            if reg_total is not None:
                g["regulation_total"] = reg_total

        # B2B flags from results log (if present) or projections
        for k in ("b2b_flag_home", "b2b_flag_away"):
            if k in df.columns:
                v = r.get(k)
                if v is not None and int(v) == 1:
                    g[k.replace("_flag", "")] = True

        # Enrich with context from daily projections
        game_id = str(r.get("game_id", ""))
        ctx = proj_ctx.get(game_id)
        if ctx is not None:
            for src, dst in [
                ("home_pace", "home_pace"), ("away_pace", "away_pace"),
                ("home_ortg", "home_ortg"), ("away_ortg", "away_ortg"),
                ("home_drtg", "home_drtg"), ("away_drtg", "away_drtg"),
            ]:
                v = _safe_float(ctx.get(src))
                if v is not None:
                    g[dst] = v
            # B2B from projections as fallback
            for flag_col, key in [("b2b_flag_home", "b2b_home"), ("b2b_flag_away", "b2b_away")]:
                if key not in g and flag_col in ctx.index:
                    v = ctx.get(flag_col)
                    if v is not None and int(v) == 1:
                        g[key] = True
            # Injury strings
            for inj_col in ("home_injuries_str", "away_injuries_str"):
                v = ctx.get(inj_col)
                if v is not None and str(v).strip():
                    g[inj_col] = str(v).strip()

        games.append(g)
    return games


def _build_nhl_graded(review_date: str) -> list[dict]:
    """Extract NHL graded plays from nhl_decisions.parquet for review_date."""
    path = os.path.join(_REPO_DIR, "nhl", "nhl_decisions.parquet")
    if not os.path.exists(path):
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(path)
        mask = (df["game_date"] == review_date)
        if "split" in df.columns:
            mask &= (df["split"] == "live")
        if "graded" in df.columns:
            mask &= (df["graded"] == 1)
        df = df[mask]
    except Exception as e:
        print(f"[ai_review] NHL parquet read failed: {e}", file=sys.stderr)
        return []

    games = []
    for _, r in df.iterrows():
        proj = _safe_float(r.get("lambda_total_calibrated"))
        actual = _safe_float(r.get("actual_total_goals_final"))
        gap = round(actual - proj, 1) if actual is not None and proj is not None else None

        g: dict[str, Any] = {
            "game_date":        review_date,
            "home_team":        str(r.get("home_team", "")),
            "away_team":        str(r.get("away_team", "")),
            "signal_side":      str(r.get("signal_side", "")),
            "confidence_tier":  str(r.get("confidence_tier", "LOW")),
            "decision_line":    _safe_float(r.get("closing_total")),
            "model_projection": proj,
            "edge_at_decision": _safe_float(r.get("edge")),
            "actual_total":     actual,
            "result":           str(r.get("result", "")),
            "projection_gap":   gap,
            "clv_directional":  _safe_float(r.get("clv_directional")),
        }
        for k in ("home_b2b", "away_b2b", "home_goalie_vs_team_baseline",
                  "away_goalie_vs_team_baseline", "home_xgf_rolling_20",
                  "away_xga_rolling_20", "home_pp_pct_rolling_20", "away_pp_pct_rolling_20"):
            if k in df.columns:
                v = _safe_float(r.get(k))
                if v is not None:
                    g[k.replace("_rolling_20", "")] = v
        games.append(g)
    return games


def _build_soccer_graded(review_date: str) -> list[dict]:
    """Extract Soccer graded plays from soccer_decisions.parquet for review_date."""
    path = os.path.join(_REPO_DIR, "soccer", "data", "soccer_decisions.parquet")
    if not os.path.exists(path):
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(path)
        mask = (df["game_date"] == review_date)
        if "split" in df.columns:
            mask &= (df["split"] == "live")
        if "graded" in df.columns:
            mask &= (df["graded"] == 1)
        df = df[mask]
    except Exception as e:
        print(f"[ai_review] Soccer parquet read failed: {e}", file=sys.stderr)
        return []

    games = []
    for _, r in df.iterrows():
        # Soccer: signal_edge is the edge, actual_over_2_5 is 0/1
        actual_over = r.get("actual_over_2_5")
        signal_side = str(r.get("signal_side", "OVER"))
        if actual_over is not None:
            result = "WIN" if (signal_side == "OVER" and actual_over == 1) or \
                              (signal_side == "UNDER" and actual_over == 0) else "LOSS"
        else:
            result = "PENDING"

        proj = _safe_float(r.get("fair_over_2_5"))  # model probability
        g: dict[str, Any] = {
            "game_date":        review_date,
            "home_team":        str(r.get("home_team", "")),
            "away_team":        str(r.get("away_team", "")),
            "league":           str(r.get("league_id", "")),
            "signal_side":      signal_side,
            "confidence_tier":  str(r.get("confidence_tier", "MEDIUM")) if "confidence_tier" in df.columns else "MEDIUM",
            "model_projection": proj,
            "edge_at_decision": _safe_float(r.get("signal_edge") or r.get("edge_over_2_5")),
            "actual_total":     _safe_float(r.get("regulation_total_90")),
            "result":           result,
        }
        games.append(g)
    return games


def _build_nfl_graded(review_date: str) -> list[dict]:
    """Extract NFL graded plays from nfl_decisions.parquet for review_date."""
    path = os.path.join(_REPO_DIR, "nfl", "data", "nfl_decisions.parquet")
    if not os.path.exists(path):
        return []
    try:
        import pandas as pd
        df = pd.read_parquet(path)
        df = df[
            (df["date"] == review_date) &
            (df["result"].isin(["WIN", "LOSS", "PUSH"]))
        ]
    except Exception as e:
        print(f"[ai_review] NFL parquet read failed: {e}", file=sys.stderr)
        return []

    games = []
    for _, r in df.iterrows():
        proj = _safe_float(r.get("model_total"))
        actual = _safe_float(r.get("total_points"))
        gap = round(actual - proj, 1) if actual is not None and proj is not None else None

        g: dict[str, Any] = {
            "game_date":        review_date,
            "home_team":        str(r.get("home_team", "")),
            "away_team":        str(r.get("away_team", "")),
            "signal_side":      str(r.get("signal_side", "")),
            "confidence_tier":  str(r.get("confidence_tier", "LOW")),
            "decision_line":    _safe_float(r.get("closing_total_line")),
            "model_projection": proj,
            "edge_at_decision": _safe_float(r.get("edge")),
            "actual_total":     actual,
            "result":           str(r.get("result", "")),
            "projection_gap":   gap,
        }
        games.append(g)
    return games


def build_graded_games(sport: str, review_date: str) -> list[dict]:
    """
    Build list of graded game dicts for the given sport and date.
    sport: 'mlb' | 'nba' | 'nhl' | 'soccer' | 'nfl'
    """
    builders = {
        "mlb":    _build_mlb_graded,
        "nba":    _build_nba_graded,
        "nhl":    _build_nhl_graded,
        "soccer": _build_soccer_graded,
        "nfl":    _build_nfl_graded,
    }
    fn = builders.get(sport.lower())
    if fn is None:
        return []
    return fn(review_date)


def build_week_games(sport: str, week_start: str, week_end: str) -> list[dict]:
    """Aggregate graded games over a date range (Mon–Sat)."""
    all_games = []
    d = date.fromisoformat(week_start)
    end = date.fromisoformat(week_end)
    while d <= end:
        all_games.extend(build_graded_games(sport, d.isoformat()))
        d += timedelta(days=1)
    return all_games


# ── Prompt builders ────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are a sharp sports betting analyst reviewing model performance for a private "
    "betting group. Write like a knowledgeable friend reviewing last night's results — "
    "analytical on the numbers, conversational on the narrative. Be honest about misses. "
    "Be specific about what the data shows. Never make up reasons — only explain misses "
    "when the feature data actually supports the explanation. Keep it concise.\n\n"
    "Never use stat abbreviations. Write for someone who knows basketball but not advanced "
    "analytics. Say 'Denver was scoring at an elite rate' not 'Denver had a 117.9 ORtg'. "
    "Say 'Philadelphia's defense was a sieve' not 'PHI DRtg was 113.7'. The numbers can "
    "appear in parentheses for context but the sentence should read naturally without them. "
    "Use 'offensive efficiency' not 'ORtg', 'defensive efficiency' not 'DRtg', "
    "'back-to-back' not 'B2B', 'closing line value' not 'CLV', 'projected' not 'proj', "
    "'final score' not 'actual'. Pace is fine as-is."
)

_SPORT_LABELS = {
    "mlb": "MLB", "nba": "NBA", "nhl": "NHL", "soccer": "Soccer", "nfl": "NFL"
}


def _roi(w: int, l: int, p: int = 0, sport: str = "mlb") -> float | None:
    if sport == "nba":
        n = w + l + p
    else:
        n = w + l
    if n == 0:
        return None
    return round((w * (100.0 / 110.0) - l) / n * 100, 1)


def _record_str(tier_games: list[dict], sport: str = "mlb") -> str:
    w = sum(1 for g in tier_games if g.get("result") == "WIN")
    l = sum(1 for g in tier_games if g.get("result") == "LOSS")
    p = sum(1 for g in tier_games if g.get("result") == "PUSH")
    roi = _roi(w, l, p, sport)
    roi_str = f", {roi:+.1f}% ROI" if roi is not None else ""
    return f"{w}-{l}-{p}{roi_str}"


def _feature_str(game: dict, sport: str) -> str:
    """Compact key-feature string for the prompt."""
    parts = []
    if sport == "mlb":
        if game.get("home_sp_xfip") is not None:
            parts.append(f"H_SP_xFIP={game['home_sp_xfip']:.2f}")
        if game.get("away_sp_xfip") is not None:
            parts.append(f"A_SP_xFIP={game['away_sp_xfip']:.2f}")
        if game.get("wind_speed") is not None:
            wd = game.get("wind_desc", "")
            parts.append(f"wind={game['wind_speed']:.0f}mph {wd}".strip())
        if game.get("temperature") is not None:
            parts.append(f"temp={game['temperature']:.0f}°F")
        if game.get("umpire_runs_factor") is not None:
            parts.append(f"ump={game['umpire_runs_factor']:.2f}")
    elif sport == "nba":
        if game.get("was_playoff"):
            parts.append("PLAYOFF")
        if game.get("went_to_ot"):
            reg = game.get("regulation_total")
            parts.append(f"OT(reg_total={reg})" if reg else "OT")
        if game.get("b2b_home"):
            parts.append("H_B2B")
        if game.get("b2b_away"):
            parts.append("A_B2B")
        if game.get("home_pace") is not None:
            parts.append(f"H_pace={game['home_pace']:.1f}")
        if game.get("away_pace") is not None:
            parts.append(f"A_pace={game['away_pace']:.1f}")
        if game.get("home_ortg") is not None:
            parts.append(f"H_ortg={game['home_ortg']:.1f}")
        if game.get("away_ortg") is not None:
            parts.append(f"A_ortg={game['away_ortg']:.1f}")
        if game.get("home_drtg") is not None:
            parts.append(f"H_drtg={game['home_drtg']:.1f}")
        if game.get("away_drtg") is not None:
            parts.append(f"A_drtg={game['away_drtg']:.1f}")
        if game.get("home_injuries_str"):
            parts.append(f"H_injuries={game['home_injuries_str']}")
        if game.get("away_injuries_str"):
            parts.append(f"A_injuries={game['away_injuries_str']}")
    elif sport == "nhl":
        if game.get("home_goalie_vs_team_baseline") is not None:
            parts.append(f"H_goalie_vs_base={game['home_goalie_vs_team_baseline']:.2f}")
        if game.get("away_goalie_vs_team_baseline") is not None:
            parts.append(f"A_goalie_vs_base={game['away_goalie_vs_team_baseline']:.2f}")
        if game.get("home_b2b"):
            parts.append("H_B2B")
        if game.get("away_b2b"):
            parts.append("A_B2B")
    elif sport == "soccer":
        if game.get("league"):
            parts.append(f"league={game['league']}")
        if game.get("edge_at_decision") is not None:
            parts.append(f"edge={game['edge_at_decision']:.3f}")
    return ", ".join(parts) if parts else "none"


def _game_block(game: dict, sport: str) -> str:
    home = game.get("home_team", "?")
    away = game.get("away_team", "?")
    side = game.get("signal_side", "?")
    line = game.get("decision_line")
    proj = game.get("model_projection")
    actual = game.get("actual_total")
    gap = game.get("projection_gap")
    result = game.get("result", "?")
    clv = game.get("clv_directional")
    feats = _feature_str(game, sport)

    line_str = f" {line}" if line is not None else ""
    proj_str = f"{proj:.1f}" if proj is not None else "?"
    actual_str = f"{actual:.1f}" if actual is not None else "?"
    gap_str = f"{gap:+.1f}" if gap is not None else "?"
    clv_str = f"{clv:+.3f}" if clv is not None else "pending"

    block = (
        f"  {away} @ {home}: {side}{line_str}\n"
        f"  Projection: {proj_str} | Actual: {actual_str} | Gap: {gap_str} | {result}\n"
        f"  Features: {feats}\n"
        f"  CLV: {clv_str}"
    )

    # For big misses, add diagnostic context
    if result == "LOSS" and gap is not None and abs(gap) >= EXPLAIN_MISS_THRESHOLD:
        direction = "MODEL TOO HIGH" if gap < 0 else "MODEL TOO LOW"
        diag = f"\n  *** BIG MISS ({direction}, {abs(gap):.1f} pts off) ***"
        if game.get("went_to_ot"):
            reg = game.get("regulation_total")
            diag += f"\n  Went to OT (regulation total: {reg})" if reg else "\n  Went to OT"
        diag += f"\n  Projection gap direction: {direction.lower()}"
        block += diag

    return block


def _build_daily_prompt(graded_games: list[dict], sport: str, review_date: str) -> str:
    sport_label = _SPORT_LABELS.get(sport.lower(), sport.upper())
    tiers = ["HIGH", "MEDIUM", "LOW"]

    sections = []
    for tier in tiers:
        tier_games = [g for g in graded_games if g.get("confidence_tier") == tier]
        if not tier_games:
            continue
        rec = _record_str(tier_games, sport)
        header = f"{tier} CONFIDENCE PLAYS ({len(tier_games)} play{'s' if len(tier_games)!=1 else ''}, {rec}):"
        if tier == "LOW":
            sections.append(header)
        else:
            lines = [header]
            for g in tier_games:
                lines.append(_game_block(g, sport))
            sections.append("\n".join(lines))

    overall_rec = _record_str(graded_games, sport)

    # Count small misses across all tiers for grouping instruction
    small_misses = [g for g in graded_games
                    if g.get("result") == "LOSS"
                    and g.get("projection_gap") is not None
                    and abs(g["projection_gap"]) < EXPLAIN_MISS_THRESHOLD]
    big_misses = [g for g in graded_games
                  if g.get("result") == "LOSS"
                  and g.get("projection_gap") is not None
                  and abs(g["projection_gap"]) >= EXPLAIN_MISS_THRESHOLD]

    small_miss_note = ""
    if small_misses:
        n = len(small_misses)
        small_miss_note = (
            f"\n\nNOTE: {n} loss{'es' if n != 1 else ''} had projection gaps under "
            f"{EXPLAIN_MISS_THRESHOLD} points. Group these together in one sentence — "
            f"they are within the model's normal variance range. Do NOT explain them individually."
        )

    big_miss_note = ""
    if big_misses:
        n = len(big_misses)
        big_miss_note = (
            f"\n\nNOTE: {n} loss{'es' if n != 1 else ''} had projection gaps of "
            f"{EXPLAIN_MISS_THRESHOLD}+ points (marked *** BIG MISS ***). "
            f"These require individual explanation — see rules below."
        )

    prompt = f"""Review yesterday's {sport_label} model performance.

DATE: {review_date}
OVERALL: {overall_rec}

{chr(10).join(sections)}{small_miss_note}{big_miss_note}

Write a results review in this structure:

1. HEADLINE (one sentence — overall record and tone)

2. HIGH TIER REVIEW
   - Record and brief performance note
   - For big misses (8+ pt gap): explain what the simulation missed (see rules below)
   - For wins: only mention if the edge was very high or the model strongly disagreed with the market
   - Skip if no HIGH plays

3. MEDIUM TIER REVIEW
   - Record and brief note
   - For big misses (8+ pt gap): explain what the simulation missed (see rules below)
   - For small misses (under 8 pts): group them in one sentence as normal variance
   - For wins: skip individual breakdown unless notable

4. LOW TIER SUMMARY
   - One sentence only: record and any pattern

5. WHAT TO WATCH
   - One or two observations about patterns in today's data relevant going forward
   - Skip if nothing notable

Rules for big misses (*** BIG MISS *** games):
  For each loss where the gap is 8+ points, reason about WHY the miss happened
  based on what the data shows — explain what the simulation MISSED, not what it SAW.

  - If model was too high (actual < projected):
    Did the game slow down below projected pace? Was there a blowout that killed
    garbage-time scoring? Did a key player get hurt during the game?

  - If model was too low (actual > projected):
    Was the pace faster than projected? Did both teams shoot unusually well?
    Did the game go to overtime? Was one team's defense worse than their
    rolling average suggested?

  Be honest when the data doesn't explain it — say "the pregame data supported
  this call and the miss looks like genuine variance" rather than inventing a reason.

  IMPORTANT: Never say "despite elite offensive efficiency" or similar as an
  explanation — that describes the pregame setup, not the miss. Focus on the
  gap between what was expected and what actually happened on the floor.

General rules:
- Be specific using the actual numbers provided
- Never invent explanations not supported by the data
- If closing line value data is available, mention whether the model beat or lost to closing lines
- Keep total length under 350 words
- Conversational but sharp — no fluff
- Never use stat abbreviations (ORtg, DRtg, B2B, CLV). Translate into plain English:
  offensive efficiency, defensive efficiency, back-to-back, closing line value.
  Numbers can appear in parentheses but the sentence must read naturally without them.
  Example: "Denver was scoring at an elite rate (117.9 pts per 100 possessions)"
  NOT: "Denver had a 117.9 ORtg" """

    return prompt


def _build_weekly_prompt(week_games: list[dict], sport: str,
                         week_start: str, week_end: str) -> str:
    sport_label = _SPORT_LABELS.get(sport.lower(), sport.upper())
    tiers = ["HIGH", "MEDIUM", "LOW"]

    # Overall record
    w = sum(1 for g in week_games if g.get("result") == "WIN")
    l = sum(1 for g in week_games if g.get("result") == "LOSS")
    p = sum(1 for g in week_games if g.get("result") == "PUSH")
    overall_roi = _roi(w, l, p, sport)
    roi_str = f" ({overall_roi:+.1f}% ROI)" if overall_roi is not None else ""

    tier_lines = []
    for tier in tiers:
        tg = [g for g in week_games if g.get("confidence_tier") == tier]
        if tg:
            tier_lines.append(f"  {tier}: {_record_str(tg, sport)}")

    # Biggest miss (largest absolute projection_gap)
    games_with_gap = [g for g in week_games if g.get("projection_gap") is not None]
    biggest_miss = max(games_with_gap, key=lambda g: abs(g["projection_gap"]), default=None)
    # Best win (WIN + largest edge)
    wins_with_edge = [g for g in week_games if g.get("result") == "WIN"
                      and g.get("edge_at_decision") is not None]
    best_win = max(wins_with_edge, key=lambda g: g["edge_at_decision"], default=None)

    # CLV summary
    has_clv = [g for g in week_games if g.get("clv_directional") is not None]
    clv_section = ""
    if has_clv:
        avg_clv = sum(g["clv_directional"] for g in has_clv) / len(has_clv)
        pct_pos = sum(1 for g in has_clv if g["clv_directional"] > 0) / len(has_clv) * 100
        coverage = len(has_clv) / len(week_games) * 100 if week_games else 0
        clv_section = f"\nCLV SUMMARY:\n  Avg CLV: {avg_clv:+.3f} | % positive: {pct_pos:.0f}% | coverage: {coverage:.0f}%"

    miss_block = ""
    if biggest_miss:
        miss_block = f"""
BIGGEST MISS THIS WEEK:
{_game_block(biggest_miss, sport)}"""

    win_block = ""
    if best_win:
        win_block = f"""
BIGGEST WIN THIS WEEK:
{_game_block(best_win, sport)}"""

    prompt = f"""Review this week's {sport_label} model performance ({week_start} to {week_end}).

WEEKLY RECORD:
  Overall: {w}-{l}-{p}{roi_str}
{chr(10).join(tier_lines)}{clv_section}{miss_block}{win_block}

Write a weekly review:

1. WEEK SUMMARY (2-3 sentences — honest overall read)

2. WHAT WORKED
   - Specific and data-backed
   - What signals or game types the model nailed

3. WHAT DIDN'T
   - Biggest miss with explanation from feature data
   - Any systematic pattern in the losses

4. MODEL HEALTH
   - Is anything drifting? Consistent bias in a direction?
   - CLV note if data available

5. HEADING INTO NEXT WEEK
   - One observation worth watching
   - No predictions — just pattern awareness

Keep under 500 words. Analytical but readable."""

    return prompt


# ── Generation ─────────────────────────────────────────────────────────────────

def _call_api(client, prompt: str, max_tokens: int) -> str | None:
    """Call Claude API. Returns text or None on failure."""
    try:
        msg = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=max_tokens,
            temperature=0,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        return msg.content[0].text if msg.content else None
    except Exception as e:
        print(f"[ai_review] API call failed: {e}", file=sys.stderr)
        return None


def _word_count(text: str) -> int:
    return len(text.split())


def _record_by_tier(graded_games: list[dict]) -> dict:
    out = {}
    for tier in ("HIGH", "MEDIUM", "LOW"):
        tg = [g for g in graded_games if g.get("confidence_tier") == tier]
        w = sum(1 for g in tg if g.get("result") == "WIN")
        l = sum(1 for g in tg if g.get("result") == "LOSS")
        p = sum(1 for g in tg if g.get("result") == "PUSH")
        if w + l + p > 0:
            out[tier] = {"w": w, "l": l, "p": p}
    w = sum(1 for g in graded_games if g.get("result") == "WIN")
    l = sum(1 for g in graded_games if g.get("result") == "LOSS")
    p = sum(1 for g in graded_games if g.get("result") == "PUSH")
    out["overall"] = {"w": w, "l": l, "p": p}
    return out


def generate_daily_review(graded_games: list[dict], sport: str,
                          review_date: str) -> dict:
    """
    Generate a daily results review narrative.
    Returns structured dict with narrative and metadata.
    """
    sport_label = _SPORT_LABELS.get(sport.lower(), sport.upper())

    if not graded_games:
        print(f"[review] No graded {sport_label} games for {review_date} — skipping")
        return {
            "generated_at":    datetime.now(timezone.utc).isoformat(),
            "date_reviewed":   review_date,
            "record_summary":  {},
            "narrative":       None,
            "generation_status": "no_games",
        }

    client = _get_client()
    if client is None:
        key = _get_api_key()
        status = "no_api_key" if not key else "client_init_failed"
        print(f"[review] {sport_label} daily review skipped: {status}", file=sys.stderr)
        return {
            "generated_at":    datetime.now(timezone.utc).isoformat(),
            "date_reviewed":   review_date,
            "record_summary":  _record_by_tier(graded_games),
            "narrative":       None,
            "generation_status": status,
        }

    print(f"[review] Generating daily {sport_label} review for {review_date}...")
    prompt = _build_daily_prompt(graded_games, sport, review_date)
    narrative = _call_api(client, prompt, max_tokens=600)

    if narrative:
        words = _word_count(narrative)
        print(f"[review] Daily {sport_label} review generated ({words} words)")
        return {
            "generated_at":    datetime.now(timezone.utc).isoformat(),
            "date_reviewed":   review_date,
            "record_summary":  _record_by_tier(graded_games),
            "narrative":       narrative,
            "generation_status": "success",
        }
    else:
        return {
            "generated_at":    datetime.now(timezone.utc).isoformat(),
            "date_reviewed":   review_date,
            "record_summary":  _record_by_tier(graded_games),
            "narrative":       None,
            "generation_status": "failed",
        }


def generate_weekly_review(week_games: list[dict], sport: str,
                           week_start: str, week_end: str) -> dict | None:
    """
    Generate a weekly results review narrative.
    Call on Sundays only. Returns dict or None if not enough data.
    """
    sport_label = _SPORT_LABELS.get(sport.lower(), sport.upper())

    if len(week_games) < 5:
        print(f"[review] Weekly {sport_label} skipped: only {len(week_games)} graded games (need 5)")
        return None

    client = _get_client()
    if client is None:
        key = _get_api_key()
        status = "no_api_key" if not key else "client_init_failed"
        print(f"[review] {sport_label} weekly review skipped: {status}", file=sys.stderr)
        return {
            "generated_at":    datetime.now(timezone.utc).isoformat(),
            "week_start":      week_start,
            "week_end":        week_end,
            "record_summary":  _record_by_tier(week_games),
            "narrative":       None,
            "generation_status": status,
        }

    print(f"[review] Generating weekly {sport_label} review ({week_start} → {week_end})...")
    prompt = _build_weekly_prompt(week_games, sport, week_start, week_end)
    narrative = _call_api(client, prompt, max_tokens=800)

    if narrative:
        words = _word_count(narrative)
        print(f"[review] Weekly {sport_label} review generated ({words} words)")
        return {
            "generated_at":    datetime.now(timezone.utc).isoformat(),
            "week_start":      week_start,
            "week_end":        week_end,
            "record_summary":  _record_by_tier(week_games),
            "narrative":       narrative,
            "generation_status": "success",
        }
    else:
        return {
            "generated_at":    datetime.now(timezone.utc).isoformat(),
            "week_start":      week_start,
            "week_end":        week_end,
            "record_summary":  _record_by_tier(week_games),
            "narrative":       None,
            "generation_status": "failed",
        }


def maybe_weekly(sport: str, today: date | None = None) -> tuple[str, str] | None:
    """
    If today is Sunday, return (week_start, week_end) for Mon–Sat.
    Otherwise return None.
    """
    d = today or date.today()
    if d.weekday() != 6:  # 6 = Sunday
        return None
    week_end = d - timedelta(days=1)    # Saturday
    week_start = d - timedelta(days=6)  # Monday
    return week_start.isoformat(), week_end.isoformat()


def is_idempotent(existing_json_path: str, review_date: str) -> bool:
    """
    Return True if the existing JSON already has a successful daily_review
    for review_date — skip regeneration.
    """
    if not os.path.exists(existing_json_path):
        return False
    try:
        with open(existing_json_path) as f:
            existing = json.load(f)
        dr = existing.get("daily_review", {}) or {}
        return (
            dr.get("date_reviewed") == review_date
            and dr.get("generation_status") == "success"
        )
    except Exception:
        return False
