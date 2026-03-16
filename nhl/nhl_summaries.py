#!/usr/bin/env python3
"""
nhl_summaries.py — Plain-English reasoning generator for NHL totals signals.

Matches the structure of generate_summary() in run_model.py:
  Sentence 1 — lead with the single highest-magnitude factor
  Sentence 2 — secondary/counter factor, or clean-read note
  Sentence 3 — always close with model vs market gap + edge bucket

Tone: texting a friend who bets. No jargon (no "lambda", "ridge", "xGF").
Max 3 sentences. Always include at least two real numbers.
"""

# NHL league average benchmarks (2024-25 season basis)
_LEAGUE_AVG_GS = 2.95   # goals scored per team per game
_LEAGUE_AVG_GA = 2.95   # goals allowed per team per game


def _gs_label(g: float) -> str:
    """Conversational label for a team's goals-per-game."""
    if g >= 3.40: return "one of the hotter offenses in the league"
    if g >= 3.15: return "above-average offense"
    if g >= 2.75: return "around the league average"
    if g >= 2.45: return "below-average offense"
    return "one of the quieter offenses in the league"


def _ga_label(g: float) -> str:
    """Conversational label for a team's goals-allowed per game."""
    if g <= 2.55: return "one of the tighter defenses in the league"
    if g <= 2.80: return "solid defensive numbers"
    if g <= 3.10: return "around the league average defensively"
    if g <= 3.40: return "giving up more than average"
    return "one of the leakier defenses in the league"


def generate_nhl_summary(signal: dict) -> str:
    """
    Generate a 2-3 sentence plain-English summary for an NHL totals signal.

    Required fields (always present in live signals):
      home_team, away_team, signal_side, closing_total,
      lambda_total_calibrated, edge, edge_bucket,
      confidence_tier, volatility_bucket, caution_flag,
      backup_flag_home, backup_flag_away,
      goalie_confirmed_home, goalie_confirmed_away

    Optional feature fields (present in signals generated after Phase 6.1):
      home_goalie_b2b, away_goalie_b2b,
      home_goalie_vs_team_baseline, away_goalie_vs_team_baseline,
      home_goals_scored_rolling_10, away_goals_scored_rolling_10,
      home_goals_allowed_rolling_10, away_goals_allowed_rolling_10,
      home_xgf_rolling_20, away_xgf_rolling_20,
      home_pp_pct_rolling_20, away_pp_pct_rolling_20,
      home_b2b, away_b2b
    """
    home    = signal.get("home_team", "")
    away    = signal.get("away_team", "")
    side    = (signal.get("signal_side") or "").upper()
    line    = signal.get("closing_total")
    lam     = signal.get("lambda_total_calibrated")
    edge    = float(signal.get("edge") or 0.0)
    ebkt    = signal.get("edge_bucket") or "0.10-0.12"
    vol     = (signal.get("volatility_bucket") or "low").lower()
    caution = int(signal.get("caution_flag") or 0)

    # Goalie status
    backup_h     = int(signal.get("backup_flag_home") or 0)
    backup_a     = int(signal.get("backup_flag_away") or 0)
    conf_h       = bool(signal.get("goalie_confirmed_home", True))
    conf_a       = bool(signal.get("goalie_confirmed_away", True))
    goalie_b2b_h = int(signal.get("home_goalie_b2b") or 0)
    goalie_b2b_a = int(signal.get("away_goalie_b2b") or 0)
    gvt_h        = float(signal.get("home_goalie_vs_team_baseline") or 0.0)
    gvt_a        = float(signal.get("away_goalie_vs_team_baseline") or 0.0)

    # Scoring form (actual current-season rolling data)
    gs_h   = signal.get("home_goals_scored_rolling_10")   # home team's goals scored/game
    gs_a   = signal.get("away_goals_scored_rolling_10")   # away team's goals scored/game
    ga_h   = signal.get("home_goals_allowed_rolling_10")  # home goals allowed/game
    ga_a   = signal.get("away_goals_allowed_rolling_10")  # away goals allowed/game

    # Team rest
    b2b_h  = int(signal.get("home_b2b") or 0)
    b2b_a  = int(signal.get("away_b2b") or 0)

    # PP (league-average priors in live pipeline — only useful if teams diverge)
    pp_h   = signal.get("home_pp_pct_rolling_20")
    pp_a   = signal.get("away_pp_pct_rolling_20")

    # Derived gap numbers
    lam_str  = f"{lam:.1f}" if lam is not None else "—"
    line_str = str(line) if line is not None else "—"
    gap      = round(lam - line, 1) if (lam is not None and line is not None) else None
    abs_gap  = abs(gap) if gap is not None else None

    # ── Factor scoring ────────────────────────────────────────────────────────
    # Score = signed contribution toward OVER (positive) or UNDER (negative).
    # For ranking we take absolute value; direction compared to signal_side
    # determines aligned vs counter.

    factors = []   # list of (name, score, description_fn)

    # 1. Backup goalie (pushes OVER — weaker goalie allows more goals)
    if backup_h:
        factors.append((
            "backup_h", +0.60,
            lambda: (
                f"{home} is rolling out a backup tonight. "
                f"That kind of goalie downgrade can add half a goal or more to what you'd otherwise expect."
            ),
        ))
    if backup_a:
        factors.append((
            "backup_a", +0.60,
            lambda: (
                f"{away} is rolling out a backup tonight. "
                f"That kind of goalie downgrade can add half a goal or more to what you'd otherwise expect."
            ),
        ))

    # 2. Goalie on back-to-back (pushes OVER — fatigue)
    if goalie_b2b_h:
        factors.append((
            "goalie_b2b_h", +0.30,
            lambda: (
                f"{home}'s goalie started last night — fatigue is a real factor "
                f"and the model bumps the opposing expected output up for it."
            ),
        ))
    if goalie_b2b_a:
        factors.append((
            "goalie_b2b_a", +0.30,
            lambda: (
                f"{away}'s goalie started last night — fatigue is a real factor "
                f"and the model bumps the opposing expected output up for it."
            ),
        ))

    # 3. Goalie quality vs baseline (positive baseline → above average → UNDER)
    if abs(gvt_h) > 0.015:
        direction = "above" if gvt_h > 0 else "below"
        pct       = f"{abs(gvt_h) * 100:.1f}"
        score     = -gvt_h * 8   # positive baseline → negative score (UNDER)
        factors.append((
            "goalie_qual_h", score,
            lambda d=direction, p=pct: (
                f"{home}'s starter is running {p}pp {d} their season save-percentage baseline — "
                f"{'keeping the puck out at an elite rate' if d == 'above' else 'letting in more than usual lately'}."
            ),
        ))
    if abs(gvt_a) > 0.015:
        direction = "above" if gvt_a > 0 else "below"
        pct       = f"{abs(gvt_a) * 100:.1f}"
        score     = -gvt_a * 8
        factors.append((
            "goalie_qual_a", score,
            lambda d=direction, p=pct: (
                f"{away}'s starter is running {p}pp {d} their season save-percentage baseline — "
                f"{'keeping the puck out at an elite rate' if d == 'above' else 'letting in more than usual lately'}."
            ),
        ))

    # 4. Away team scoring form (low away offense → UNDER; high → OVER)
    if gs_a is not None:
        dev = gs_a - _LEAGUE_AVG_GS
        if abs(dev) > 0.20:
            label = _gs_label(gs_a)
            score = dev * 1.2   # positive = above avg = OVER lean
            factors.append((
                "gs_away", score,
                lambda gs=gs_a, lb=label: (
                    f"{away} has been averaging {gs:.1f} goals per game over their last 10 — "
                    f"{lb}."
                ),
            ))

    # 5. Home team defense form (low goals allowed → UNDER; high → OVER)
    if ga_h is not None:
        dev = ga_h - _LEAGUE_AVG_GA
        if abs(dev) > 0.20:
            label = _ga_label(ga_h)
            score = dev * 1.2   # higher GA = OVER lean
            factors.append((
                "ga_home", score,
                lambda ga=ga_h, lb=label: (
                    f"{home} has been allowing {ga:.1f} goals per game over their last 10 — {lb}."
                ),
            ))

    # 6. Home team scoring form (high home offense → OVER; low → UNDER)
    if gs_h is not None:
        dev = gs_h - _LEAGUE_AVG_GS
        if abs(dev) > 0.20:
            label = _gs_label(gs_h)
            score = dev * 1.2
            factors.append((
                "gs_home", score,
                lambda gs=gs_h, lb=label: (
                    f"{home} has been scoring {gs:.1f} goals per game at home over their last 10 — {lb}."
                ),
            ))

    # 7. Away team defense form (high GA away → OVER)
    if ga_a is not None:
        dev = ga_a - _LEAGUE_AVG_GA
        if abs(dev) > 0.20:
            label = _ga_label(ga_a)
            score = dev * 1.2
            factors.append((
                "ga_away", score,
                lambda ga=ga_a, lb=label: (
                    f"{away} has been allowing {ga:.1f} goals per game over their last 10 — {lb}."
                ),
            ))

    # 8. Team back-to-back (pushes UNDER for the B2B team)
    if b2b_h and not backup_h and not goalie_b2b_h:
        factors.append((
            "team_b2b_h", -0.20,
            lambda: (
                f"{home} is on a back-to-back tonight — the model applies a rest penalty "
                f"that nudges the total lower."
            ),
        ))
    if b2b_a and not backup_a and not goalie_b2b_a:
        factors.append((
            "team_b2b_a", -0.20,
            lambda: (
                f"{away} is on a back-to-back tonight — the model applies a rest penalty "
                f"that nudges the total lower."
            ),
        ))

    # 9. PP mismatch (only if materially above league avg ~0.20 and gap > 0.04)
    if (pp_h is not None and pp_a is not None and
            abs(pp_h - pp_a) > 0.04 and
            max(pp_h, pp_a) > 0.225):
        better_team = home if pp_h > pp_a else away
        better_pp   = max(pp_h, pp_a)
        dev         = (pp_h + pp_a) / 2 - 0.205
        factors.append((
            "pp", dev * 4,
            lambda bt=better_team, pp=better_pp: (
                f"{bt} is converting at {pp * 100:.1f}% on the power play lately — "
                f"hot special teams can push the total either way."
            ),
        ))

    # ── Determine aligned vs counter relative to signal_side ─────────────────
    # UNDER signal: negative score = aligned; positive = counter
    # OVER signal:  positive score = aligned; negative = counter

    def _is_aligned(score: float) -> bool:
        return (side == "UNDER" and score < 0) or (side == "OVER" and score > 0)

    aligned  = sorted([f for f in factors if _is_aligned(f[1])],
                      key=lambda x: abs(x[1]), reverse=True)
    counters = sorted([f for f in factors if not _is_aligned(f[1])],
                      key=lambda x: abs(x[1]), reverse=True)

    # ── Build sentences ───────────────────────────────────────────────────────
    sentences = []
    used_names: set[str] = set()

    # Sentence 1 — top aligned factor, or model/market gap if none
    if aligned:
        top = aligned[0]
        sentences.append(top[2]())
        used_names.add(top[0])
    else:
        # Fallback: lead with the model/market gap (always has real numbers)
        direction  = "below" if side == "UNDER" else "above"
        direction2 = "under" if side == "UNDER" else "over"
        abs_g_str  = f"{abs_gap:.1f}" if abs_gap is not None else "?"
        sentences.append(
            f"We're projecting {lam_str} combined goals here — "
            f"that's {abs_g_str} {direction} the {line_str} line, "
            f"a gap the market hasn't priced in."
        )
        used_names.add("model_gap")

    # Sentence 2 — secondary aligned factor, counter-factor, vol note, or clean read
    s2 = None

    # Try a second aligned factor (different from top)
    for f in aligned[1:]:
        if f[0] not in used_names and abs(f[1]) >= 0.18:
            s2 = f"On top of that, {f[2]()[0].lower()}{f[2]()[1:]}"
            used_names.add(f[0])
            break

    # If no second aligned factor, try a counter-factor
    if s2 is None and counters and abs(counters[0][1]) >= 0.18:
        s2 = f"{counters[0][2]()} That pulls the other way, but not enough to flip the lean."
        used_names.add(counters[0][0])

    # Vol note if high
    if s2 is None and vol == "high":
        s2 = (
            "This is a high-volatility matchup — backup or fatigued goalie plus "
            "a penalty-heavy environment means the distribution is wider than usual."
        )

    # Clean-read note when no strong secondary factor and both goalies locked in
    if s2 is None and not backup_h and not backup_a and not goalie_b2b_h and not goalie_b2b_a:
        if gs_h is not None and gs_a is not None:
            combined = round(gs_h + gs_a, 1)
            s2 = (
                f"Both starting goalies are confirmed. "
                f"Recent form has these teams combining for {combined:.1f} goals per game — "
                f"{'reinforcing the under' if side == 'UNDER' else 'supporting the over'}."
            )
        else:
            s2 = (
                "Both starting goalies are confirmed with no backup or fatigue concerns — "
                "a clean read without the usual volatility caveats."
            )

    if s2:
        sentences.append(s2)

    # Sentence 3 — always close with model vs market gap + edge bucket
    close = (
        f"Model has {lam_str}, market is at {line_str} — "
        f"{side.lower()} by {abs_gap:.1f} goals ({ebkt} edge)."
        if abs_gap is not None else
        f"Model has {lam_str} vs the {line_str} line ({ebkt} edge)."
    )
    if caution:
        close += " ⚠️ 6.5-line overs are a caution bucket for this model."
    sentences.append(close)

    return " ".join(sentences[:3])
