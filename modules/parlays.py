"""
modules/parlays.py — Build multi-leg parlay cards from today's plays + props.

Three tiers:
  parlay_3 — ⭐⭐⭐ only, up to 3 legs  (SHARP CARD)
  parlay_5 — ⭐⭐+,    up to 5 legs  (VALUE CARD)
  parlay_7 — ⭐+,      up to 7 legs  (HIGH RISK / HIGH REWARD)

Dedup rules:
  - One leg per game_pk (only one of: full total, F5 total, any prop for that game)
  - No duplicate player names across prop legs
"""

_STAR_ORDER = {"⭐⭐⭐": 0, "⭐⭐": 1, "⭐": 2}

_MIN_STARS = {
    "parlay_3": {"⭐⭐⭐"},
    "parlay_5": {"⭐⭐⭐", "⭐⭐"},
    "parlay_7": {"⭐⭐⭐", "⭐⭐", "⭐"},
}


def _build_pool(plays: list[dict]) -> list[dict]:
    """
    Build a flat list of candidate legs from plays (game total, F5, and props).
    Each leg has all fields needed for display + dedup.
    """
    pool = []

    for b in plays:
        game   = b.get("game", {})
        proj   = b.get("proj", {})
        fe     = b.get("full_edge", {})
        f5e    = b.get("f5_edge", {})
        rating = b.get("rating", "")

        if rating not in _STAR_ORDER:
            continue

        game_pk = game.get("game_pk")
        matchup = f"{game.get('away_team', '')} @ {game.get('home_team', '')}"
        lean    = proj.get("lean", "NEUTRAL")
        cscore  = float(proj.get("confidence_score") or 0)

        # ── game total leg ────────────────────────────────────────────────────
        if lean in ("OVER", "UNDER"):
            proj_full = proj.get("proj_total_full")
            line_full = fe.get("consensus")
            edge_full = fe.get("edge")
            if proj_full:
                label = (
                    f"{lean} {float(line_full):.1f}" if line_full is not None
                    else f"{lean} {float(proj_full):.1f}"
                )
                pool.append({
                    "game_pk":         game_pk,
                    "player_name":     None,
                    "matchup":         matchup,
                    "market":          "full",
                    "market_label":    label,
                    "rating":          rating,
                    "projection":      float(proj_full),
                    "line":            float(line_full) if line_full is not None else None,
                    "lean":            lean,
                    "edge":            float(edge_full) if edge_full is not None else None,
                    "confidence_score": cscore,
                })

        # ── F5 leg ────────────────────────────────────────────────────────────
        proj_f5 = proj.get("proj_total_f5")
        line_f5 = f5e.get("consensus")
        edge_f5 = f5e.get("edge")
        f5_lean = f5e.get("lean")
        if proj_f5 and line_f5 is not None and f5_lean in ("OVER", "UNDER"):
            pool.append({
                "game_pk":         game_pk,
                "player_name":     None,
                "matchup":         matchup,
                "market":          "f5",
                "market_label":    f"F5 {f5_lean} {float(line_f5):.1f}",
                "rating":          rating,
                "projection":      float(proj_f5),
                "line":            float(line_f5),
                "lean":            f5_lean,
                "edge":            float(edge_f5) if edge_f5 is not None else None,
                "confidence_score": cscore,
            })

        # ── prop legs ─────────────────────────────────────────────────────────
        for p in (b.get("props") or []):
            if not p.get("is_play"):
                continue
            market = p.get("market", "")
            plean  = p.get("lean", "OVER")
            pline  = p.get("line")
            pproj  = p.get("projection")
            pedge  = p.get("edge")
            pname  = p.get("player_name") or ""
            if not pname or pline is None or pproj is None:
                continue

            if market == "K":
                label = f"OVER {float(pline):.1f} Ks"
            elif market == "TB":
                label = f"OVER {float(pline):.1f} TB"
            else:
                label = f"{plean} {float(pline):.1f} {market}"

            pool.append({
                "game_pk":         game_pk,
                "player_name":     pname,
                "matchup":         matchup,
                "market":          market,
                "market_label":    label,
                "rating":          rating,
                "projection":      float(pproj),
                "line":            float(pline),
                "lean":            plean,
                "edge":            float(pedge) if pedge is not None else None,
                "confidence_score": cscore,
            })

    return pool


def _select_legs(pool: list[dict], min_stars: set, max_legs: int) -> list[dict]:
    """Filter, sort, and dedup pool down to max_legs."""
    eligible = [leg for leg in pool if leg["rating"] in min_stars]
    eligible.sort(key=lambda l: (
        _STAR_ORDER.get(l["rating"], 3),
        -abs(l["edge"] or 0),
        -l["confidence_score"],
    ))

    used_games   = set()
    used_players = set()
    legs = []

    for leg in eligible:
        if leg["game_pk"] in used_games:
            continue
        pname = leg.get("player_name")
        if pname and pname in used_players:
            continue

        used_games.add(leg["game_pk"])
        if pname:
            used_players.add(pname)
        legs.append(leg)
        if len(legs) >= max_legs:
            break

    return legs


def build_all_parlays(plays: list[dict]) -> dict:
    """
    Build parlay_3, parlay_5, parlay_7 from the plays list.
    Each value is a list of leg dicts (empty list if fewer than 2 legs available).
    """
    pool = _build_pool(plays)
    p3 = _select_legs(pool, _MIN_STARS["parlay_3"], 3)
    p5 = _select_legs(pool, _MIN_STARS["parlay_5"], 5)
    p7 = _select_legs(pool, _MIN_STARS["parlay_7"], 7)

    return {
        "parlay_3": p3 if len(p3) >= 2 else [],
        "parlay_5": p5 if len(p5) >= 2 else [],
        "parlay_7": p7 if len(p7) >= 2 else [],
    }
