"""
Props projections module — pitcher K total and batter total bases.

Formulas
--------
Pitcher Ks:
    base_k      = (k_per_9 / 9) * expected_ip
    opp_adj     = opp_k_rate / LEAGUE_AVG_K_RATE        # how strikeout-prone is the lineup?
    ump_adj     = umpire_factor                          # 1.0 if unknown
    park_adj    = park_k_factor                          # 1.0 if unknown
    proj_ks     = base_k * opp_adj * ump_adj * park_adj
    NOTE: swstr_adj removed — K/9 already embeds SwStr% effect; multiplying by swstr_adj double-counts

Batter total bases:
    xslg_adj    = xslg (or slg fallback)
    base_tb     = xslg_adj * expected_ab
    gb_factor   = 1 - 0.4 * (gb_pct - LEAGUE_AVG_GB_PCT)  # high GB pitcher → fewer XBH
    wind_adj    = 1.0 / 0.95 / 1.05 depending on direction+speed
    park_adj    = park_factor (linear: 1.10 park → +10% TB)
    proj_tb     = base_tb * gb_factor * wind_adj * park_adj
"""

from __future__ import annotations

from typing import Optional

from modules.props_data import (
    LEAGUE_AVG_GB_PCT,
    LEAGUE_AVG_K_RATE,
    LEAGUE_AVG_SWSTR,
    LEAGUE_AVG_XSLG,
    get_pitcher_k_profile,
    get_team_k_rate,
    get_team_top_batters,
)

# Expected IP for a starting pitcher — used when we have no profile
DEFAULT_SP_IP = 5.5
# Expected ABs for a batter in a full game
DEFAULT_AB = 3.8

# Edges below this are not shown as plays
EDGE_PLAY_THRESHOLD = 0.10   # 10 %


# ── Pitcher K projection ────────────────────────────────────────────────────────

def project_pitcher_ks(
    profile: dict,
    opp_k_rate: float,
    expected_ip: Optional[float] = None,
    umpire_factor: float = 1.0,
    park_k_factor: float = 1.0,
) -> float:
    """Return projected strikeout total for a starting pitcher."""
    k9    = profile.get("k_per_9") or 0
    swstr = profile.get("swstr_pct") or LEAGUE_AVG_SWSTR
    raw_ip = expected_ip if expected_ip is not None else profile.get("avg_ip_per_start") or DEFAULT_SP_IP
    ip    = raw_ip if 3.0 <= raw_ip <= 6.5 else DEFAULT_SP_IP

    # Regression to the mean: small samples inflate K/9 volatility.
    # Blend toward LEAGUE_AVG_K9 scaled by total season IP (full trust at 150+ IP).
    from modules.props_data import LEAGUE_AVG_K9
    total_ip   = profile.get("ip") or 0
    reliability = min(total_ip / 150.0, 1.0)
    k9 = reliability * k9 + (1.0 - reliability) * LEAGUE_AVG_K9

    base_k    = (k9 / 9) * ip
    opp_adj   = opp_k_rate / LEAGUE_AVG_K_RATE   if LEAGUE_AVG_K_RATE > 0 else 1.0

    # Cap opp_adj so one extreme lineup doesn't blow up the result
    opp_adj   = max(0.70, min(opp_adj, 1.20))

    # swstr_adj intentionally omitted: K/9 already embeds SwStr% effect
    proj = base_k * opp_adj * umpire_factor * park_k_factor
    return round(proj, 2)


# ── Batter total-bases projection ───────────────────────────────────────────────

def _wind_tb_adj(wind_desc: Optional[str], wind_mph: Optional[float]) -> float:
    """
    Estimate wind impact on total bases.
    Blowing out (to CF) at 10+ mph → slight boost; blowing in → slight penalty.
    """
    if not wind_desc:
        return 1.0
    wd  = wind_desc.lower()
    mph = float(wind_mph or 0)
    if "dome" in wd:
        return 1.0
    adj = 0.0
    if ("out to" in wd or "blowing out" in wd):
        adj = +0.04 if mph >= 15 else +0.02 if mph >= 10 else 0.0
    elif ("in from" in wd or "blowing in" in wd):
        adj = -0.04 if mph >= 15 else -0.02 if mph >= 10 else 0.0
    return 1.0 + adj


def project_batter_tb(
    batter: dict,
    pitcher_gb_pct: Optional[float] = None,
    wind_desc: Optional[str] = None,
    wind_mph: Optional[float] = None,
    park_factor: Optional[float] = None,
    expected_ab: float = DEFAULT_AB,
) -> float:
    """Return projected total bases for a single batter."""
    pa          = batter.get("pa") or 0
    # Regression to the mean: small samples (< 400 PA) inflate xSLG dramatically.
    # A backup with 60 PA of lucky xSLG=0.63 should not project like Juan Soto.
    reliability = min(pa / 400.0, 1.0)
    raw_xslg    = batter.get("xslg") or batter.get("slg") or LEAGUE_AVG_XSLG
    xslg        = reliability * raw_xslg + (1.0 - reliability) * LEAGUE_AVG_XSLG

    # Scale expected AB by PA as a proxy for lineup position.
    # Regular starters accumulate 400+ PA and bat high in the order (more ABs);
    # backups and part-timers bat lower and get fewer plate appearances per game.
    # Range: 2.8 AB (spot starts / < 50 PA) to 4.2 AB (full-time regular 400+ PA).
    if expected_ab == DEFAULT_AB:
        expected_ab = 2.8 + reliability * 1.4

    # High GB pitcher → more grounders → fewer XBH
    gb_pct  = pitcher_gb_pct if pitcher_gb_pct is not None else LEAGUE_AVG_GB_PCT
    gb_diff = gb_pct - LEAGUE_AVG_GB_PCT          # positive → more GBs than avg
    gb_factor = 1.0 - 0.40 * gb_diff              # 10 ppt above avg ≈ -4% TB
    gb_factor = max(0.80, min(gb_factor, 1.20))

    wind_adj = _wind_tb_adj(wind_desc, wind_mph)

    pf       = park_factor if park_factor is not None else 1.0
    park_adj = max(0.85, min(pf, 1.20))

    proj = xslg * expected_ab * gb_factor * wind_adj * park_adj

    # Scale to market: raw formula produces ~2x DraftKings lines.
    # 0.75x factor + 2.5 cap brings elite hitters (Judge, Seager) to 1.5–1.8 range.
    proj = proj * 0.75
    proj = min(proj, 2.5)
    return round(proj, 2)


# ── Edge calculation ─────────────────────────────────────────────────────────────

def _edge(proj: float, line: float) -> dict:
    """
    Return edge dict:
      lean    — "OVER" / "UNDER" / None
      edge    — raw difference (proj - line)
      edge_pct— abs((proj - line) / line)
      is_play — True if |edge_pct| >= EDGE_PLAY_THRESHOLD
    """
    if line is None or line <= 0:
        return {"lean": None, "edge": None, "edge_pct": None, "is_play": False}
    diff     = proj - line
    edge_pct = abs(diff / line)
    lean     = "OVER" if diff > 0 else "UNDER"
    return {
        "lean":     lean,
        "edge":     round(diff, 2),
        "edge_pct": round(edge_pct, 4),
        "is_play":  edge_pct >= EDGE_PLAY_THRESHOLD,
    }


# ── Game-level entry point ────────────────────────────────────────────────────────

def get_game_props(
    game: dict,
    home_sp_name: Optional[str],
    away_sp_name: Optional[str],
    factors: dict,
    umpire: Optional[dict],
    pitcher_k_db: dict,
    batter_db: dict,
    props_lines: dict,
) -> list[dict]:
    """
    Build all prop projections for a single game.

    Parameters
    ----------
    game          — game dict with home_team / away_team keys
    home_sp_name  — home starting pitcher name (may be None / "TBD")
    away_sp_name  — away starting pitcher name
    factors       — factors dict from run_model: park_factor, wind_desc, wind_speed
    umpire        — umpire dict with "k_factor" key (1.0 if unknown)
    pitcher_k_db  — from build_pitcher_k_db()
    batter_db     — from build_batter_props_db()
    props_lines   — dict keyed by player_name → {"k": float, "tb": float}
                    (values may be missing if no line found)

    Returns
    -------
    List of prop dicts, one per (player, market):
        {
          player_name, team, market,       # "K" | "TB"
          projection, line,
          lean, edge, edge_pct, is_play,
          profile_summary,                 # brief debug string
        }
    """
    home_team = (game.get("home_team") or "").upper()
    away_team = (game.get("away_team") or "").upper()

    park_factor  = factors.get("park_factor")  or 1.0
    wind_desc    = factors.get("wind_desc")
    wind_speed   = factors.get("wind_speed")

    ump_k_factor = (umpire or {}).get("k_factor", 1.0) or 1.0
    park_k_factor = 1.0  # park K factor treated as neutral unless we have ballpark data

    props = []

    # ── Pitcher K props ──────────────────────────────────────────────────────────
    for sp_name, opp_team in [(away_sp_name, home_team), (home_sp_name, away_team)]:
        if not sp_name or sp_name.strip().upper() in ("TBD", ""):
            continue
        profile = get_pitcher_k_profile(sp_name, pitcher_k_db)
        if profile is None:
            continue

        opp_k_rate = get_team_k_rate(opp_team, batter_db)
        proj_k     = project_pitcher_ks(
            profile,
            opp_k_rate   = opp_k_rate,
            umpire_factor= ump_k_factor,
            park_k_factor= park_k_factor,
        )

        line_k = (props_lines.get(sp_name.lower()) or {}).get("k")
        edge_d = _edge(proj_k, line_k)

        props.append({
            "player_name":     profile["name"],
            "team":            profile.get("team", ""),
            "market":          "K",
            "projection":      proj_k,
            "line":            line_k,
            **edge_d,
            "profile_summary": (
                f"K/9={profile.get('k_per_9', 0):.1f} "
                f"SwStr={profile.get('swstr_pct', 0):.3f} "
                f"IP={profile.get('avg_ip_per_start', DEFAULT_SP_IP):.1f} "
                f"OppK={opp_k_rate:.3f}"
            ),
        })

    # ── Batter total-bases props ─────────────────────────────────────────────────
    for team, sp_name in [(home_team, away_sp_name), (away_team, home_sp_name)]:
        # We need the opposing pitcher's profile for GB% adjustment
        opp_profile  = get_pitcher_k_profile(sp_name, pitcher_k_db) if sp_name else None
        opp_gb_pct   = (opp_profile or {}).get("gb_pct")

        top_batters  = get_team_top_batters(team, batter_db, n=3)
        for batter in top_batters:
            bname  = batter["name"]
            proj_tb = project_batter_tb(
                batter,
                pitcher_gb_pct = opp_gb_pct,
                wind_desc      = wind_desc,
                wind_mph       = wind_speed,
                park_factor    = park_factor,
            )

            line_tb = (props_lines.get(bname.lower()) or {}).get("tb")
            edge_d  = _edge(proj_tb, line_tb)

            props.append({
                "player_name":     bname,
                "team":            team,
                "market":          "TB",
                "projection":      proj_tb,
                "line":            line_tb,
                **edge_d,
                "profile_summary": (
                    f"xSLG={batter.get('xslg') or batter.get('slg', 0):.3f} "
                    f"barrel={batter.get('barrel_pct') or 0:.3f} "
                    f"OppGB={opp_gb_pct:.3f}" if opp_gb_pct else
                    f"xSLG={batter.get('xslg') or batter.get('slg', 0):.3f} "
                    f"barrel={batter.get('barrel_pct') or 0:.3f}"
                ),
            })

    return props
