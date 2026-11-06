"""
CC-1 cells.py — Cell definitions for the corrcause screen.
This is the forward object (CHECK 3): same code runs the screen and the forward test.
Thresholds read from CELLS_v1.json (mirrors the registry §4/§5 exactly).
"""

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
CELLS_CONFIG = ROOT / "CELLS_v1.json"

from research.corrcause.build_tables import (
    american_to_implied, v_american_to_implied, SOFT_BOOKS, nhl_full_to_abbrev
)


def load_config():
    with open(CELLS_CONFIG) as f:
        return json.load(f)


def devig_pair(price_h, price_a):
    """De-vig a pair of American odds to (fair_h, fair_a)."""
    imp_h = american_to_implied(price_h)
    imp_a = american_to_implied(price_a)
    if pd.isna(imp_h) or pd.isna(imp_a) or (imp_h + imp_a) == 0:
        return np.nan, np.nan
    total = imp_h + imp_a
    return imp_h / total, imp_a / total


# =====================================================================
#  NHL TIER 1 CELLS
# =====================================================================

def nh1_total_pushed_down(games, features, config):
    """NH1: Pinnacle total close ≤ opener - 0.5. Side: OVER."""
    thresh = config["NH1"]["total_step"]  # 0.5
    mask = (
        games["pin_open_total"].notna() &
        games["pin_close_total"].notna() &
        (games["pin_close_total"] <= games["pin_open_total"] - thresh) &
        games["over"].notna()
    )
    fired = games[mask].copy()
    fired["cell_side"] = "over"
    fired["residual"] = fired["over"] - fired["pin_close_fair_over"]
    return fired


def nh2_total_pushed_up(games, features, config):
    """NH2: Pinnacle total close ≥ opener + 0.5. Side: UNDER."""
    thresh = config["NH2"]["total_step"]
    mask = (
        games["pin_open_total"].notna() &
        games["pin_close_total"].notna() &
        (games["pin_close_total"] >= games["pin_open_total"] + thresh) &
        games["over"].notna()
    )
    fired = games[mask].copy()
    fired["cell_side"] = "under"
    fired["residual"] = (1 - fired["over"]) - fired["pin_close_fair_under"]
    return fired


def nh3_soft_only_ml_move(games, features, config):
    """NH3: Soft book moved ≥3 pts from its own opener while Pinnacle moved <1 pt. Side: AGAINST."""
    thresh_soft = config["NH3"]["soft_move_pts"]  # 3.0
    thresh_pin = config["NH3"]["pin_move_pts"]    # 1.0
    # For each soft book in {DK, FD, BetMGM}, check the move
    results = []
    for book in ["draftkings", "fanduel", "betmgm"]:
        soft_close_h = f"soft_{book}_close_ml_h"
        # We need soft opener too — not available separately. Skip this cell for now.
        # NH3 requires soft book OPENER, which we don't have separately per book.
        pass
    # NH3 requires per-book openers which are not in the current games table.
    # Return empty — this cell needs additional data extraction.
    return pd.DataFrame()


def nh4_backup_goalie_overshoot(games, features, config):
    """NH4: Backup goalie AND Pinnacle ML moved ≥2 pts against. Side: backup's team."""
    thresh_ml_move = config["NH4"]["ml_move_pts"]  # 2.0
    gf = games.merge(features[["event_id", "home_is_backup", "away_is_backup",
                                "home_starter_gsax", "home_primary_gsax",
                                "away_starter_gsax", "away_primary_gsax",
                                "pin_ml_move_h"]].rename(
                                    columns={"pin_ml_move_h": "feat_ml_move_h"}),
                     on="event_id", how="left")

    results = []
    # Home backup: ML moved against home (pin_close_fair_h < pin_open_fair_h by ≥ thresh)
    mask_h = (
        (gf["home_is_backup"] == 1) &
        gf["pin_close_fair_h"].notna() & gf["pin_open_fair_h"].notna() &
        ((gf["pin_open_fair_h"] - gf["pin_close_fair_h"]) * 100 >= thresh_ml_move) &
        gf["home_win"].notna()
    )
    h_fired = gf[mask_h].copy()
    h_fired["cell_side"] = "home_ml"
    h_fired["residual"] = h_fired["home_win"].astype(float) - h_fired["pin_close_fair_h"]
    results.append(h_fired)

    # Away backup
    mask_a = (
        (gf["away_is_backup"] == 1) &
        gf["pin_close_fair_a"].notna() & gf["pin_open_fair_a"].notna() &
        ((gf["pin_open_fair_a"] - gf["pin_close_fair_a"]) * 100 >= thresh_ml_move) &
        gf["home_win"].notna()
    )
    a_fired = gf[mask_a].copy()
    a_fired["cell_side"] = "away_ml"
    a_fired["residual"] = (1 - a_fired["home_win"].astype(float)) - a_fired["pin_close_fair_a"]
    results.append(a_fired)

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def nh5_post_ot_road_b2b_travel(games, features, config):
    """NH5: Game 2 of B2B, road, game 1 went to OT/SO, ≥1 TZ change. Side: opponent ML."""
    gf = games.merge(features[["event_id", "home_b2b", "away_b2b",
                                "home_last_game_ot", "away_last_game_ot",
                                "home_rest_days", "away_rest_days"]],
                     on="event_id", how="left")

    results = []
    # Away team is the road team at home venue
    # "Road B2B": away_b2b == 1, away_last_game_ot == 1
    # TZ change: would need venue mapping — simplified to just B2B + OT for now
    mask_a = (
        (gf["away_b2b"] == 1) &
        (gf["away_last_game_ot"] == 1) &
        gf["home_win"].notna()
    )
    fired = gf[mask_a].copy()
    fired["cell_side"] = "home_ml"  # opponent = home team
    fired["residual"] = fired["home_win"].astype(float) - fired["pin_close_fair_h"]
    results.append(fired)

    # Home team road B2B: home_b2b == 1, home_last_game_ot == 1
    # (Home team is at home, so this doesn't apply — NH5 is road only)

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def nh6_en_inflated_favourite(games, features, config):
    """NH6: Favourite (p_fair ≥ 0.58) with EN-inflated goal diff. Side: underdog ML."""
    # EN goal data not yet in features — need to add in build_tables.
    # Skip for now.
    return pd.DataFrame()


def nh7_both_rested(games, features, config):
    """NH7: Both teams rest ≥ 4 days. Side: UNDER."""
    thresh = config["NH7"]["rest_days"]  # 4
    gf = games.merge(features[["event_id", "home_rest_days", "away_rest_days"]],
                     on="event_id", how="left")
    mask = (
        (gf["home_rest_days"] >= thresh) &
        (gf["away_rest_days"] >= thresh) &
        gf["over"].notna()
    )
    fired = gf[mask].copy()
    fired["cell_side"] = "under"
    fired["residual"] = (1 - fired["over"]) - fired["pin_close_fair_under"]
    return fired


# =====================================================================
#  NBA TIER 1 CELLS
# =====================================================================

def nb1_total_suppressed(games, features, config):
    """NB1: Pinnacle total close ≤ opener - 3.0. Side: OVER."""
    thresh = config["NB1"]["total_drop"]  # 3.0
    mask = (
        games["pin_open_total"].notna() &
        games["pin_close_total"].notna() &
        (games["pin_close_total"] <= games["pin_open_total"] - thresh) &
        games["over"].notna()
    )
    fired = games[mask].copy()
    fired["cell_side"] = "over"
    fired["residual"] = fired["over"] - fired["pin_close_fair_over"]
    return fired


def nb2_total_raised(games, features, config):
    """NB2: Pinnacle total close ≥ opener + 3.0. Side: UNDER."""
    thresh = config["NB2"]["total_raise"]
    mask = (
        games["pin_open_total"].notna() &
        games["pin_close_total"].notna() &
        (games["pin_close_total"] >= games["pin_open_total"] + thresh) &
        games["over"].notna()
    )
    fired = games[mask].copy()
    fired["cell_side"] = "under"
    fired["residual"] = (1 - fired["over"]) - fired["pin_close_fair_under"]
    return fired


def nb3_soft_only_spread_move(games, features, config):
    """NB3: Soft book spread moved ≥1.5 while Pinnacle moved <0.5. Side: against the move."""
    # Requires per-book spread openers — not available. Skip.
    return pd.DataFrame()


def nb5_eastbound_3in4_fatigue(games, features, config):
    """NB5: 3rd game in 4 nights, road, ≥2 TZ eastward. Side: opponent ATS."""
    gf = games.merge(features[["event_id", "away_3in4", "away_rest_days"]],
                     on="event_id", how="left")
    # Simplified: away team 3-in-4
    mask = (
        (gf["away_3in4"] == 1) &
        gf["home_covers"].notna()
    )
    fired = gf[mask].copy()
    fired["cell_side"] = "home_ats"
    fired["residual"] = fired["home_covers"] - 0.5  # ATS residual vs 50%
    return fired


def nb6_ot_fatigue_b2b(games, features, config):
    """NB6: B2B when game 1 went to OT. Side: opponent ATS."""
    gf = games.merge(features[["event_id", "home_b2b", "away_b2b",
                                "home_last_ot", "away_last_ot"]],
                     on="event_id", how="left")
    results = []
    # Away team OT-B2B
    mask_a = (
        (gf["away_b2b"] == 1) &
        (gf["away_last_ot"] == 1) &
        gf["home_covers"].notna()
    )
    fired_a = gf[mask_a].copy()
    fired_a["cell_side"] = "home_ats"
    fired_a["residual"] = fired_a["home_covers"] - 0.5
    results.append(fired_a)

    # Home team OT-B2B
    mask_h = (
        (gf["home_b2b"] == 1) &
        (gf["home_last_ot"] == 1) &
        gf["home_covers"].notna()
    )
    fired_h = gf[mask_h].copy()
    fired_h["cell_side"] = "away_ats"
    fired_h["residual"] = (1 - fired_h["home_covers"]) - 0.5
    results.append(fired_h)

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def nb7_early_season_pace_anchor(games, features, config):
    """NB7: League-wide early-season anchor. EXPLORATORY."""
    # Needs league pts/game comparison with prior season — complex, one DEV season.
    return pd.DataFrame()


def nb8_rest_premium_overshoot(games, features, config):
    """NB8: Home ≥3 days rest vs away B2B. Side: B2B team ATS."""
    thresh_rest = config["NB8"]["home_rest_days"]  # 3
    gf = games.merge(features[["event_id", "home_rest_days", "away_b2b"]],
                     on="event_id", how="left")
    mask = (
        (gf["home_rest_days"] >= thresh_rest) &
        (gf["away_b2b"] == 1) &
        gf["home_covers"].notna()
    )
    fired = gf[mask].copy()
    fired["cell_side"] = "away_ats"
    fired["residual"] = (1 - fired["home_covers"]) - 0.5
    return fired


# =====================================================================
#  TIER 1 REGISTRY
# =====================================================================

NHL_TIER1 = {
    "NH1": nh1_total_pushed_down,
    "NH2": nh2_total_pushed_up,
    "NH3": nh3_soft_only_ml_move,
    "NH4": nh4_backup_goalie_overshoot,
    "NH5": nh5_post_ot_road_b2b_travel,
    "NH6": nh6_en_inflated_favourite,
    "NH7": nh7_both_rested,
}

NBA_TIER1 = {
    "NB1": nb1_total_suppressed,
    "NB2": nb2_total_raised,
    "NB3": nb3_soft_only_spread_move,
    "NB5": nb5_eastbound_3in4_fatigue,
    "NB6": nb6_ot_fatigue_b2b,
    "NB7": nb7_early_season_pace_anchor,
    "NB8": nb8_rest_premium_overshoot,
}


# =====================================================================
#  TIER 2 GENERATOR
# =====================================================================

def generate_tier2_nhl(games, features, config):
    """Generate all NHL Tier 2 cells from the grammar."""
    cells = []
    # Features: opener ML band, opener total band, ML move band, total move band,
    # soft-Pinnacle divergence, move timing, book dispersion, in-play reset
    gf = games.merge(features, on="event_id", how="left", suffixes=("", "_feat"))

    # Market sides: ML(H/A), total(O/U)
    sides = [
        ("home_ml", "home_win", "pin_close_fair_h", True),
        ("away_ml", "home_win", "pin_close_fair_a", False),
        ("over", "over", "pin_close_fair_over", True),
        ("under", "over", "pin_close_fair_under", False),
    ]

    tier2_features = {}

    # Opener total band: 5.5 / 6.0 / 6.5+
    if "pin_open_total" in gf.columns:
        gf["opener_total_band"] = pd.cut(
            gf["pin_open_total"], bins=[0, 5.75, 6.25, 20],
            labels=["5.5", "6.0", "6.5+"]
        )
        tier2_features["opener_total_band"] = ["5.5", "6.0", "6.5+"]

    # Total move band: down step / flat / up step
    if "pin_total_move" in gf.columns:
        pin_tm = gf["pin_total_move"].copy()
        # Use features version if main column has suffix
        if "pin_total_move_feat" in gf.columns:
            pin_tm = gf["pin_total_move_feat"]
        gf["total_move_band"] = pd.cut(
            pin_tm, bins=[-10, -0.25, 0.25, 10],
            labels=["down", "flat", "up"]
        )
        tier2_features["total_move_band"] = ["down", "flat", "up"]

    # ML move band
    if "pin_ml_move_h" in gf.columns:
        ml_move = gf["pin_ml_move_h"].copy()
        if "pin_ml_move_h_feat" in gf.columns:
            ml_move = gf["pin_ml_move_h_feat"]
        gf["ml_move_band"] = pd.cut(
            ml_move, bins=[-50, -3, 3, 50],
            labels=["le-3", "flat", "ge+3"]
        )
        tier2_features["ml_move_band"] = ["le-3", "flat", "ge+3"]

    # Opener ML band (fair home prob)
    if "pin_open_fair_h" in gf.columns:
        gf["opener_ml_band"] = pd.cut(
            gf["pin_open_fair_h"], bins=[0, 0.45, 0.55, 1.0],
            labels=["away_fav", "close", "home_fav"]
        )
        tier2_features["opener_ml_band"] = ["away_fav", "close", "home_fav"]

    for feat_name, levels in tier2_features.items():
        for level in levels:
            for side_name, outcome_col, fair_col, is_positive in sides:
                mask = (gf[feat_name] == level) & gf[outcome_col].notna() & gf[fair_col].notna()
                fired = gf[mask].copy()
                if len(fired) == 0:
                    continue

                if is_positive:
                    if outcome_col == "home_win":
                        fired["residual"] = fired[outcome_col].astype(float) - fired[fair_col]
                    else:
                        fired["residual"] = fired[outcome_col].astype(float) - fired[fair_col]
                else:
                    if outcome_col == "home_win":
                        fired["residual"] = (1 - fired[outcome_col].astype(float)) - fired[fair_col]
                    else:
                        fired["residual"] = (1 - fired[outcome_col].astype(float)) - fired[fair_col]

                cell_id = f"T2_NHL_{feat_name}_{level}_{side_name}"
                cells.append({
                    "cell_id": cell_id,
                    "sport": "nhl",
                    "tier": 2,
                    "feature": feat_name,
                    "level": level,
                    "side": side_name,
                    "n_fired": len(fired),
                    "data": fired,
                })

    return cells


def generate_tier2_nba(games, features, config):
    """Generate all NBA Tier 2 cells from the grammar."""
    cells = []
    gf = games.merge(features, on="event_id", how="left", suffixes=("", "_feat"))

    sides = [
        ("home_ml", "home_win", "pin_close_fair_h", True),
        ("away_ml", "home_win", "pin_close_fair_a", False),
        ("home_ats", "home_covers", None, True),  # ATS uses 0.5 baseline
        ("away_ats", "home_covers", None, False),
        ("over", "over", "pin_close_fair_over", True),
        ("under", "over", "pin_close_fair_under", False),
    ]

    tier2_features = {}

    # Rest days H/A bins: 0, 1, 2, 3+
    for side in ["home", "away"]:
        col = f"{side}_rest_days"
        if col in gf.columns:
            gf[f"{col}_bin"] = gf[col].apply(
                lambda x: "0" if x == 0 else ("1" if x == 1 else ("2" if x == 2 else "3+"))
                if not pd.isna(x) else np.nan
            )
            tier2_features[f"{col}_bin"] = ["0", "1", "2", "3+"]

    # B2B flags
    for col in ["home_b2b", "away_b2b", "home_3in4", "away_3in4"]:
        if col in gf.columns:
            gf[f"{col}_flag"] = gf[col].apply(lambda x: "yes" if x == 1 else "no" if x == 0 else np.nan)
            tier2_features[f"{col}_flag"] = ["yes", "no"]

    # Streak bins
    for side in ["home", "away"]:
        col = f"{side}_streak"
        if col in gf.columns:
            gf[f"{col}_bin"] = gf[col].apply(
                lambda x: "win3+" if x >= 3 else ("loss3+" if x <= -3 else "other")
                if not pd.isna(x) else np.nan
            )
            tier2_features[f"{col}_bin"] = ["win3+", "loss3+", "other"]

    # Last margin band
    for side in ["home", "away"]:
        col = f"{side}_last_margin"
        if col in gf.columns:
            gf[f"{col}_bin"] = gf[col].apply(
                lambda x: "blowout_loss" if x <= -15 else ("blowout_win" if x >= 15 else "normal")
                if not pd.isna(x) else np.nan
            )
            tier2_features[f"{col}_bin"] = ["blowout_loss", "blowout_win", "normal"]

    # Opener total band
    if "pin_open_total" in gf.columns:
        gf["opener_total_band"] = pd.cut(
            gf["pin_open_total"], bins=[0, 220, 230, 500],
            labels=["lt220", "220-230", "gt230"]
        )
        tier2_features["opener_total_band"] = ["lt220", "220-230", "gt230"]

    # Total move band
    pin_tm = gf.get("pin_total_move", gf.get("pin_total_move_feat"))
    if pin_tm is not None:
        gf["total_move_band"] = pd.cut(
            pin_tm, bins=[-50, -2, 2, 50],
            labels=["le-2", "flat", "ge+2"]
        )
        tier2_features["total_move_band"] = ["le-2", "flat", "ge+2"]

    # Spread move band
    if "pin_spread_move_h" in gf.columns:
        gf["spread_move_band"] = pd.cut(
            gf["pin_spread_move_h"], bins=[-50, -1.5, 1.5, 50],
            labels=["le-1.5", "flat", "ge+1.5"]
        )
        tier2_features["spread_move_band"] = ["le-1.5", "flat", "ge+1.5"]

    # Month
    if "month" in gf.columns:
        gf["month_str"] = gf["month"].astype(str)
        tier2_features["month_str"] = [str(m) for m in sorted(gf["month"].dropna().unique().astype(int))]

    # Weekday
    if "weekday" in gf.columns:
        gf["weekday_str"] = gf["weekday"].astype(str)
        tier2_features["weekday_str"] = [str(w) for w in sorted(gf["weekday"].dropna().unique().astype(int))]

    for feat_name, levels in tier2_features.items():
        for level in levels:
            for side_name, outcome_col, fair_col, is_positive in sides:
                if outcome_col not in gf.columns:
                    continue

                mask = (gf[feat_name] == level) & gf[outcome_col].notna()
                if fair_col and fair_col in gf.columns:
                    mask = mask & gf[fair_col].notna()

                fired = gf[mask].copy()
                if len(fired) == 0:
                    continue

                if fair_col and fair_col in gf.columns:
                    if is_positive:
                        fired["residual"] = fired[outcome_col].astype(float) - fired[fair_col]
                    else:
                        fired["residual"] = (1 - fired[outcome_col].astype(float)) - fired[fair_col]
                else:
                    # ATS: residual vs 0.5
                    if is_positive:
                        fired["residual"] = fired[outcome_col].astype(float) - 0.5
                    else:
                        fired["residual"] = (1 - fired[outcome_col].astype(float)) - 0.5

                cell_id = f"T2_NBA_{feat_name}_{level}_{side_name}"
                cells.append({
                    "cell_id": cell_id,
                    "sport": "nba",
                    "tier": 2,
                    "feature": feat_name,
                    "level": level,
                    "side": side_name,
                    "n_fired": len(fired),
                    "data": fired,
                })

    return cells
