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
    american_to_implied, v_american_to_implied, SOFT_BOOKS
)


def load_config():
    with open(CELLS_CONFIG) as f:
        return json.load(f)


def _merge_features(games, features, cols):
    """Merge specific feature columns into games, avoiding duplicates."""
    need = [c for c in cols if c not in games.columns]
    if not need:
        return games.copy()
    return games.merge(features[["event_id"] + need], on="event_id", how="left")


def _devig_spread(price_h, price_a):
    """De-vig spread prices to fair home-covers probability."""
    imp_h = american_to_implied(price_h)
    imp_a = american_to_implied(price_a)
    if pd.isna(imp_h) or pd.isna(imp_a) or (imp_h + imp_a) == 0:
        return np.nan
    return imp_h / (imp_h + imp_a)


# =====================================================================
#  NHL TIER 1
# =====================================================================

def nh1_total_pushed_down(games, features, config):
    """NH1: Pinnacle total close ≤ opener − 0.5. Side: OVER."""
    thresh = config["NH1"]["total_step"]
    mask = (
        games["pin_open_total"].notna() & games["pin_close_total"].notna() &
        (games["pin_close_total"] <= games["pin_open_total"] - thresh) &
        games["over"].notna() & games["pin_close_fair_over"].notna()
    )
    fired = games[mask].copy()
    fired["cell_side"] = "over"
    fired["residual"] = fired["over"] - fired["pin_close_fair_over"]
    return fired


def nh2_total_pushed_up(games, features, config):
    """NH2: Pinnacle total close ≥ opener + 0.5. Side: UNDER."""
    thresh = config["NH2"]["total_step"]
    mask = (
        games["pin_open_total"].notna() & games["pin_close_total"].notna() &
        (games["pin_close_total"] >= games["pin_open_total"] + thresh) &
        games["over"].notna() & games["pin_close_fair_under"].notna()
    )
    fired = games[mask].copy()
    fired["cell_side"] = "under"
    fired["residual"] = (1 - fired["over"]) - fired["pin_close_fair_under"]
    return fired


def nh3_soft_only_ml_move(games, features, config):
    """NH3: Soft book moved ≥3 imp pts from its own opener while Pinnacle moved <1 pt.
    Side: AGAINST the soft move, at that book's price."""
    thresh_soft = config["NH3"]["soft_move_pts"]  # 3.0 implied prob pts
    thresh_pin = config["NH3"]["pin_move_pts"]    # 1.0

    results = []
    for book in ["draftkings", "fanduel", "betmgm"]:
        soft_open_h = f"soft_{book}_open_ml_h"
        soft_close_h = f"soft_{book}_close_ml_h"
        if soft_open_h not in games.columns or soft_close_h not in games.columns:
            continue

        gf = games.copy()
        # De-vig soft book's opener and close
        gf["soft_open_imp_h"] = gf[soft_open_h].apply(american_to_implied)
        gf["soft_close_imp_h"] = gf[soft_close_h].apply(american_to_implied)
        # Pinnacle opener/close imp
        gf["pin_open_imp_h"] = gf["pin_open_ml_h"].apply(american_to_implied)
        gf["pin_close_imp_h"] = gf["pin_close_ml_h"].apply(american_to_implied)

        gf["soft_move_h"] = (gf["soft_close_imp_h"] - gf["soft_open_imp_h"]) * 100
        gf["pin_move_h"] = (gf["pin_close_imp_h"] - gf["pin_open_imp_h"]) * 100

        # Soft moved ≥ thresh in either direction, Pinnacle < thresh in same direction
        for direction in [1, -1]:
            if direction == 1:
                # Soft moved home UP ≥ 3 pts, pin < 1 pt in same direction
                mask = (
                    gf["soft_move_h"].notna() & gf["pin_move_h"].notna() &
                    (gf["soft_move_h"] >= thresh_soft) &
                    (gf["pin_move_h"] < thresh_pin) &
                    gf["home_win"].notna() & gf["pin_close_fair_a"].notna()
                )
                fired = gf[mask].copy()
                fired["cell_side"] = "away_ml"  # against the soft home-up move
                fired["residual"] = (1 - fired["home_win"].astype(float)) - fired["pin_close_fair_a"]
                fired["nh3_book"] = book
            else:
                mask = (
                    gf["soft_move_h"].notna() & gf["pin_move_h"].notna() &
                    (gf["soft_move_h"] <= -thresh_soft) &
                    (gf["pin_move_h"] > -thresh_pin) &
                    gf["home_win"].notna() & gf["pin_close_fair_h"].notna()
                )
                fired = gf[mask].copy()
                fired["cell_side"] = "home_ml"  # against the soft away-up move
                fired["residual"] = fired["home_win"].astype(float) - fired["pin_close_fair_h"]
                fired["nh3_book"] = book

            if len(fired) > 0:
                results.append(fired)

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def nh4_backup_goalie_overshoot(games, features, config):
    """NH4: Backup goalie AND Pinnacle ML moved ≥2 pts against. Side: backup's team."""
    thresh = config["NH4"]["ml_move_pts"]
    gf = _merge_features(games, features, [
        "home_is_backup", "away_is_backup",
        "home_starter_gsax", "home_primary_gsax",
        "away_starter_gsax", "away_primary_gsax",
    ])

    results = []
    # Home backup: pin moved AGAINST home ≥ thresh (pin_open_fair_h - pin_close_fair_h ≥ thresh/100)
    mask_h = (
        (gf["home_is_backup"] == 1) &
        gf["pin_close_fair_h"].notna() & gf["pin_open_fair_h"].notna() &
        ((gf["pin_open_fair_h"] - gf["pin_close_fair_h"]) * 100 >= thresh) &
        gf["home_win"].notna()
    )
    h = gf[mask_h].copy()
    h["cell_side"] = "home_ml"
    h["residual"] = h["home_win"].astype(float) - h["pin_close_fair_h"]
    results.append(h)

    # Away backup
    mask_a = (
        (gf["away_is_backup"] == 1) &
        gf["pin_close_fair_a"].notna() & gf["pin_open_fair_a"].notna() &
        ((gf["pin_open_fair_a"] - gf["pin_close_fair_a"]) * 100 >= thresh) &
        gf["home_win"].notna()
    )
    a = gf[mask_a].copy()
    a["cell_side"] = "away_ml"
    a["residual"] = (1 - a["home_win"].astype(float)) - a["pin_close_fair_a"]
    results.append(a)

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def nh5_post_ot_road_b2b_travel(games, features, config):
    """NH5: Away team on B2B, game 1 went OT/SO, ≥1 TZ change between venues. Side: home ML."""
    gf = _merge_features(games, features, [
        "away_b2b", "away_last_game_ot", "away_tz_change",
    ])
    mask = (
        (gf["away_b2b"] == 1) &
        (gf["away_last_game_ot"] == 1) &
        gf["away_tz_change"].notna() &
        (gf["away_tz_change"].abs() >= 1) &
        gf["home_win"].notna() & gf["pin_close_fair_h"].notna()
    )
    fired = gf[mask].copy()
    fired["cell_side"] = "home_ml"
    fired["residual"] = fired["home_win"].astype(float) - fired["pin_close_fair_h"]
    return fired


def nh6_en_inflated_favourite(games, features, config):
    """NH6: Favourite (p_fair ≥ 0.58) with EN-inflated record. Side: underdog ML."""
    thresh_fair = config["NH6"]["fav_fair_min"]
    thresh_en = config["NH6"]["en_net_min"]

    gf = _merge_features(games, features, ["home_en_net_15", "away_en_net_15"])

    results = []
    # Home is favourite
    mask_h = (
        gf["pin_close_fair_h"].notna() &
        (gf["pin_close_fair_h"] >= thresh_fair) &
        gf["home_en_net_15"].notna() &
        (gf["home_en_net_15"] >= thresh_en) &
        gf["home_win"].notna() & gf["pin_close_fair_a"].notna()
    )
    h = gf[mask_h].copy()
    h["cell_side"] = "away_ml"  # underdog
    h["residual"] = (1 - h["home_win"].astype(float)) - h["pin_close_fair_a"]
    results.append(h)

    # Away is favourite
    mask_a = (
        gf["pin_close_fair_a"].notna() &
        (gf["pin_close_fair_a"] >= thresh_fair) &
        gf["away_en_net_15"].notna() &
        (gf["away_en_net_15"] >= thresh_en) &
        gf["home_win"].notna() & gf["pin_close_fair_h"].notna()
    )
    a = gf[mask_a].copy()
    a["cell_side"] = "home_ml"  # underdog
    a["residual"] = a["home_win"].astype(float) - a["pin_close_fair_h"]
    results.append(a)

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def nh7_both_rested(games, features, config):
    """NH7: Both teams rest ≥ 4 days. Side: UNDER."""
    thresh = config["NH7"]["rest_days"]
    gf = _merge_features(games, features, ["home_rest_days", "away_rest_days"])
    mask = (
        (gf["home_rest_days"] >= thresh) & (gf["away_rest_days"] >= thresh) &
        gf["over"].notna() & gf["pin_close_fair_under"].notna()
    )
    fired = gf[mask].copy()
    fired["cell_side"] = "under"
    fired["residual"] = (1 - fired["over"]) - fired["pin_close_fair_under"]
    return fired


# =====================================================================
#  NBA TIER 1
# =====================================================================

def nb1_total_suppressed(games, features, config):
    """NB1: Pinnacle total close ≤ opener − 3.0. Side: OVER."""
    thresh = config["NB1"]["total_drop"]
    mask = (
        games["pin_open_total"].notna() & games["pin_close_total"].notna() &
        (games["pin_close_total"] <= games["pin_open_total"] - thresh) &
        games["over"].notna() & games["pin_close_fair_over"].notna()
    )
    fired = games[mask].copy()
    fired["cell_side"] = "over"
    fired["residual"] = fired["over"] - fired["pin_close_fair_over"]
    return fired


def nb2_total_raised(games, features, config):
    """NB2: Pinnacle total close ≥ opener + 3.0. Side: UNDER."""
    thresh = config["NB2"]["total_raise"]
    mask = (
        games["pin_open_total"].notna() & games["pin_close_total"].notna() &
        (games["pin_close_total"] >= games["pin_open_total"] + thresh) &
        games["over"].notna() & games["pin_close_fair_under"].notna()
    )
    fired = games[mask].copy()
    fired["cell_side"] = "under"
    fired["residual"] = (1 - fired["over"]) - fired["pin_close_fair_under"]
    return fired


def nb3_soft_only_spread_move(games, features, config):
    """NB3: Soft book spread moved ≥1.5 from its opener while Pinnacle <0.5. Side: against."""
    thresh_soft = config["NB3"]["soft_move_pts"]  # 1.5 pts
    thresh_pin = config["NB3"]["pin_move_pts"]    # 0.5

    results = []
    for book in ["draftkings", "fanduel", "betmgm"]:
        soft_open_col = f"soft_{book}_open_spread_h"
        soft_close_col = f"soft_{book}_close_spread_h"
        if soft_open_col not in games.columns or soft_close_col not in games.columns:
            continue

        gf = games.copy()
        gf["soft_spr_move"] = gf[soft_close_col] - gf[soft_open_col]
        gf["pin_spr_move"] = gf["pin_close_spread_h"] - gf["pin_open_spread_h"]

        # Pinnacle spread fair prob for ATS
        gf["pin_spread_fair_h"] = gf.apply(
            lambda r: _devig_spread(r.get("pin_close_spread_h_price"), r.get("pin_close_spread_a_price")),
            axis=1
        )

        # Soft moved home spread ≥ thresh (more negative = more points to home)
        for direction in [1, -1]:
            if direction == -1:
                # Soft moved spread MORE negative (giving home more pts) by ≥ 1.5
                mask = (
                    gf["soft_spr_move"].notna() & gf["pin_spr_move"].notna() &
                    (gf["soft_spr_move"] <= -thresh_soft) &
                    (gf["pin_spr_move"] > -thresh_pin) &
                    gf["home_covers"].notna() & gf["pin_spread_fair_h"].notna()
                )
                fired = gf[mask].copy()
                fired["cell_side"] = "away_ats"  # against the home-favoring move
                fired["residual"] = (1 - fired["home_covers"]) - (1 - fired["pin_spread_fair_h"])
            else:
                mask = (
                    gf["soft_spr_move"].notna() & gf["pin_spr_move"].notna() &
                    (gf["soft_spr_move"] >= thresh_soft) &
                    (gf["pin_spr_move"] < thresh_pin) &
                    gf["home_covers"].notna() & gf["pin_spread_fair_h"].notna()
                )
                fired = gf[mask].copy()
                fired["cell_side"] = "home_ats"
                fired["residual"] = fired["home_covers"] - fired["pin_spread_fair_h"]

            fired["nb3_book"] = book
            if len(fired) > 0:
                results.append(fired)

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def nb5_eastbound_3in4_fatigue(games, features, config):
    """NB5: Away team's 3rd game in 4 nights, on the road, ≥2 TZ eastward. Side: home ATS."""
    gf = _merge_features(games, features, [
        "away_games_last_4", "away_rest_days",
    ])

    # Need venue TZ for the eastward check
    from research.corrcause.build_tables import get_venue_tz, _NBA_ABBREV
    nba_tz = get_venue_tz().get("nba", {})

    # 3rd game in 4 nights: away_games_last_4 >= 2 (prior games in last 4 days ≥ 2)
    # On the road: away team (automatic)
    # ≥2 TZ eastward: venue of game-1 TZ - current venue TZ ≤ -2
    # We approximate: current venue = home_team's TZ, game-1 venue unknown from features alone
    # For now, use away team's HOME TZ as proxy for where they started the stretch
    # TODO: proper game-1 venue tracking

    # Compute TZ difference: away team's home TZ minus current venue (home team) TZ
    # Eastward = negative TZ change (e.g., LAL at BOS = -8 - (-5) = -3, 3 hours east)
    results = []
    for _, row in gf.iterrows():
        if pd.isna(row.get("away_games_last_4")) or row["away_games_last_4"] < 2:
            continue
        if pd.isna(row.get("home_covers")):
            continue

        away_full = row["away_team"]
        home_full = row["home_team"]
        away_home_tz = nba_tz.get(away_full, np.nan)
        venue_tz = nba_tz.get(home_full, np.nan)
        if pd.isna(away_home_tz) or pd.isna(venue_tz):
            continue
        tz_diff = venue_tz - away_home_tz  # positive = eastward
        if tz_diff < 2:
            continue

        results.append(row)

    if not results:
        return pd.DataFrame()

    fired = pd.DataFrame(results)

    # ATS residual vs Pinnacle fair
    fired["pin_spread_fair_h"] = fired.apply(
        lambda r: _devig_spread(r.get("pin_close_spread_h_price"), r.get("pin_close_spread_a_price")),
        axis=1
    )
    fired = fired[fired["pin_spread_fair_h"].notna()].copy()
    fired["cell_side"] = "home_ats"
    fired["residual"] = fired["home_covers"] - fired["pin_spread_fair_h"]
    return fired


def nb6_ot_fatigue_b2b(games, features, config):
    """NB6: B2B when game 1 went to OT. Side: opponent ATS."""
    gf = _merge_features(games, features, [
        "home_b2b", "away_b2b", "home_last_ot", "away_last_ot",
    ])

    # Spread fair prob
    gf["pin_spread_fair_h"] = gf.apply(
        lambda r: _devig_spread(r.get("pin_close_spread_h_price"), r.get("pin_close_spread_a_price")),
        axis=1
    )

    results = []
    # Away team OT-B2B → side: home ATS
    mask_a = (
        (gf["away_b2b"] == 1) & (gf["away_last_ot"] == 1) &
        gf["home_covers"].notna() & gf["pin_spread_fair_h"].notna()
    )
    a = gf[mask_a].copy()
    a["cell_side"] = "home_ats"
    a["residual"] = a["home_covers"] - a["pin_spread_fair_h"]
    results.append(a)

    # Home team OT-B2B → side: away ATS
    mask_h = (
        (gf["home_b2b"] == 1) & (gf["home_last_ot"] == 1) &
        gf["home_covers"].notna() & gf["pin_spread_fair_h"].notna()
    )
    h = gf[mask_h].copy()
    h["cell_side"] = "away_ats"
    h["residual"] = (1 - h["home_covers"]) - (1 - h["pin_spread_fair_h"])
    results.append(h)

    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()


def nb7_early_season_pace_anchor(games, features, config):
    """NB7: Early-season pace anchor. EXPLORATORY, 2023-24 only.
    2022-23 window cannot run: no 2021-22 pts/game on disk."""
    # Only run on season 2023 (2023-24)
    gf = games[games["season"] == 2023].copy()
    if len(gf) == 0:
        return pd.DataFrame()

    # Prior season (2022-23) full-season pts/game
    # Use box_stats to compute it
    from pathlib import Path
    box = pd.read_parquet(Path.home() / "mlb-model/nba/data/box_stats.parquet")
    prior_season = box[box["season"] == "2022-23"]
    prior_ppg = prior_season["pts"].mean()
    print(f"    NB7: 2022-23 full-season pts/game = {prior_ppg:.1f}")

    # Window: season tip through Nov 15
    gf["game_date"] = pd.to_datetime(gf["commence_time"]).dt.tz_convert("US/Eastern").dt.date
    window_end = pd.Timestamp("2023-11-15").date()
    window = gf[gf["game_date"] <= window_end].copy()
    if len(window) == 0:
        return pd.DataFrame()

    # For each date D: league pts/game over games before D in 2023-24
    current_season = box[box["season"] == "2023-24"].copy()
    current_season["date_dt"] = pd.to_datetime(current_season["date"])

    results = []
    for _, row in window.iterrows():
        gd = row["game_date"]
        prior_games = current_season[current_season["date_dt"].dt.date < gd]
        if len(prior_games) < 40:
            continue
        current_ppg = prior_games["pts"].mean()
        gap = current_ppg - prior_ppg

        if abs(gap) < 2.0:
            continue

        if pd.isna(row.get("over")) or pd.isna(row.get("pin_close_fair_over")):
            continue

        r = row.copy()
        if gap >= 2.0:
            r["cell_side"] = "over"
            r["residual"] = row["over"] - row["pin_close_fair_over"]
        else:
            r["cell_side"] = "under"
            r["residual"] = (1 - row["over"]) - row["pin_close_fair_under"]
        r["nb7_gap"] = gap
        results.append(r)

    if not results:
        return pd.DataFrame()
    return pd.DataFrame(results)


def nb8_rest_premium_overshoot(games, features, config):
    """NB8: Home ≥3 days rest vs away B2B. Side: away ATS."""
    thresh_rest = config["NB8"]["home_rest_days"]
    gf = _merge_features(games, features, ["home_rest_days", "away_b2b"])

    gf["pin_spread_fair_h"] = gf.apply(
        lambda r: _devig_spread(r.get("pin_close_spread_h_price"), r.get("pin_close_spread_a_price")),
        axis=1
    )

    mask = (
        (gf["home_rest_days"] >= thresh_rest) & (gf["away_b2b"] == 1) &
        gf["home_covers"].notna() & gf["pin_spread_fair_h"].notna()
    )
    fired = gf[mask].copy()
    fired["cell_side"] = "away_ats"
    fired["residual"] = (1 - fired["home_covers"]) - (1 - fired["pin_spread_fair_h"])
    return fired


# =====================================================================
#  REGISTRIES
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
#  TIER 2 GENERATORS
# =====================================================================

def generate_tier2_nhl(games, features, config, market_features=None):
    """NHL Tier 2: v1 features + v2 market-behaviour features × bins × sides."""
    gf = games.merge(features, on="event_id", how="left", suffixes=("", "_feat"))
    if market_features is not None:
        mf_cols = [c for c in market_features.columns if c != "event_id"]
        mf_need = [c for c in mf_cols if c not in gf.columns]
        if mf_need:
            gf = gf.merge(market_features[["event_id"] + mf_need], on="event_id", how="left")
    cells = []

    # Market sides for NHL: ML(H/A), total(O/U)
    sides = [
        ("home_ml", lambda df: df["home_win"].astype(float) - df["pin_close_fair_h"],
         lambda df: df["home_win"].notna() & df["pin_close_fair_h"].notna()),
        ("away_ml", lambda df: (1 - df["home_win"].astype(float)) - df["pin_close_fair_a"],
         lambda df: df["home_win"].notna() & df["pin_close_fair_a"].notna()),
        ("over", lambda df: df["over"] - df["pin_close_fair_over"],
         lambda df: df["over"].notna() & df["pin_close_fair_over"].notna()),
        ("under", lambda df: (1 - df["over"]) - df["pin_close_fair_under"],
         lambda df: df["over"].notna() & df["pin_close_fair_under"].notna()),
    ]

    feat_bins = {}
    # Opener total band
    if "pin_open_total" in gf.columns:
        gf["opener_total_band"] = pd.cut(gf["pin_open_total"], bins=[0, 5.75, 6.25, 20],
                                          labels=["5.5", "6.0", "6.5+"])
        feat_bins["opener_total_band"] = ["5.5", "6.0", "6.5+"]

    # Total move
    tm = gf["pin_total_move"] if "pin_total_move" in gf.columns else gf.get("pin_total_move_feat")
    if tm is not None:
        gf["total_move_band"] = pd.cut(tm, bins=[-10, -0.25, 0.25, 10], labels=["down", "flat", "up"])
        feat_bins["total_move_band"] = ["down", "flat", "up"]

    # ML move
    ml = gf["pin_ml_move_h"] if "pin_ml_move_h" in gf.columns else gf.get("pin_ml_move_h_feat")
    if ml is not None:
        gf["ml_move_band"] = pd.cut(ml, bins=[-50, -3, 3, 50], labels=["le-3", "flat", "ge+3"])
        feat_bins["ml_move_band"] = ["le-3", "flat", "ge+3"]

    # Opener ML band
    if "pin_open_fair_h" in gf.columns:
        gf["opener_ml_band"] = pd.cut(gf["pin_open_fair_h"], bins=[0, 0.45, 0.55, 1.0],
                                       labels=["away_fav", "close", "home_fav"])
        feat_bins["opener_ml_band"] = ["away_fav", "close", "home_fav"]

    # --- V2 market-behaviour features ---
    # f1: soft-Pinnacle divergence (abs)
    if "f1_max_div_abs" in gf.columns:
        valid = gf["f1_max_div_abs"].notna()
        gf.loc[valid, "f1_divergence_band"] = pd.cut(
            gf.loc[valid, "f1_max_div_abs"],
            bins=[0.02, 0.04, 0.07, 1.0], labels=["small", "medium", "large"],
            include_lowest=True
        )
        # Also a "none" bin for games with no divergence ≥ 0.02
        gf["f1_divergence_flag"] = gf["f1_max_div_abs"].apply(
            lambda x: "yes" if not pd.isna(x) else "no"
        )
        feat_bins["f1_divergence_flag"] = ["yes", "no"]
        feat_bins["f1_divergence_band"] = ["small", "medium", "large"]

    # f2: move timing share
    if "f2_timing_share" in gf.columns:
        valid = gf["f2_timing_share"].notna()
        gf.loc[valid, "f2_timing_band"] = gf.loc[valid, "f2_timing_share"].apply(
            lambda x: "early" if x < 0.3 else ("mixed" if x < 0.7 else "late")
        )
        feat_bins["f2_timing_band"] = ["early", "mixed", "late"]

    # f3: book-consensus dispersion (terciles)
    if "f3_dispersion" in gf.columns:
        valid = gf["f3_dispersion"].notna()
        if valid.sum() >= 30:
            terciles = gf.loc[valid, "f3_dispersion"].quantile([1/3, 2/3])
            gf.loc[valid, "f3_dispersion_band"] = gf.loc[valid, "f3_dispersion"].apply(
                lambda x: "low" if x <= terciles.iloc[0] else ("mid" if x <= terciles.iloc[1] else "high")
            )
            feat_bins["f3_dispersion_band"] = ["low", "mid", "high"]

    # f4: in-play reset (NOT-BETTABLE, diagnostic only)
    if "f4_ip_reset_delta" in gf.columns:
        gf["f4_reset_flag"] = gf["f4_ip_reset_delta"].apply(
            lambda x: "yes" if not pd.isna(x) else "no"
        )
        feat_bins["f4_reset_flag"] = ["yes", "no"]

    for feat, levels in feat_bins.items():
        for level in levels:
            for side_name, resid_fn, valid_fn in sides:
                mask = (gf[feat] == level) & valid_fn(gf)
                fired = gf[mask].copy()
                if len(fired) == 0:
                    continue
                fired["residual"] = resid_fn(fired)
                fired["cell_side"] = side_name
                cell_id = f"T2_NHL_{feat}_{level}_{side_name}"
                is_f4 = feat.startswith("f4_")
                cells.append({
                    "cell_id": cell_id,
                    "sport": "nhl", "tier": 2,
                    "feature": feat, "level": level, "side": side_name,
                    "n_fired": len(fired), "data": fired,
                    "not_bettable": is_f4,
                })

    return cells


def generate_tier2_nba(games, features, config, market_features=None):
    """NBA Tier 2: v1 features + v2 market-behaviour features × bins × sides."""
    gf = games.merge(features, on="event_id", how="left", suffixes=("", "_feat"))
    if market_features is not None:
        mf_cols = [c for c in market_features.columns if c != "event_id"]
        mf_need = [c for c in mf_cols if c not in gf.columns]
        if mf_need:
            gf = gf.merge(market_features[["event_id"] + mf_need], on="event_id", how="left")

    # Spread fair prob
    gf["pin_spread_fair_h"] = gf.apply(
        lambda r: _devig_spread(r.get("pin_close_spread_h_price"), r.get("pin_close_spread_a_price")),
        axis=1
    )

    sides = [
        ("home_ml", lambda df: df["home_win"].astype(float) - df["pin_close_fair_h"],
         lambda df: df["home_win"].notna() & df["pin_close_fair_h"].notna()),
        ("away_ml", lambda df: (1 - df["home_win"].astype(float)) - df["pin_close_fair_a"],
         lambda df: df["home_win"].notna() & df["pin_close_fair_a"].notna()),
        ("home_ats", lambda df: df["home_covers"] - df["pin_spread_fair_h"],
         lambda df: df["home_covers"].notna() & df["pin_spread_fair_h"].notna()),
        ("away_ats", lambda df: (1 - df["home_covers"]) - (1 - df["pin_spread_fair_h"]),
         lambda df: df["home_covers"].notna() & df["pin_spread_fair_h"].notna()),
        ("over", lambda df: df["over"] - df["pin_close_fair_over"],
         lambda df: df["over"].notna() & df["pin_close_fair_over"].notna()),
        ("under", lambda df: (1 - df["over"]) - df["pin_close_fair_under"],
         lambda df: df["over"].notna() & df["pin_close_fair_under"].notna()),
    ]

    feat_bins = {}

    # Rest days bins
    for side in ["home", "away"]:
        col = f"{side}_rest_days"
        if col in gf.columns:
            gf[f"{col}_bin"] = gf[col].apply(
                lambda x: "0" if x == 0 else ("1" if x == 1 else ("2" if x == 2 else "3+"))
                if not pd.isna(x) else np.nan
            )
            feat_bins[f"{col}_bin"] = ["0", "1", "2", "3+"]

    # B2B/3in4 flags
    for col in ["home_b2b", "away_b2b", "home_3in4", "away_3in4"]:
        if col in gf.columns:
            gf[f"{col}_flag"] = gf[col].apply(lambda x: "yes" if x == 1 else ("no" if x == 0 else np.nan))
            feat_bins[f"{col}_flag"] = ["yes", "no"]

    # Streaks
    for side in ["home", "away"]:
        col = f"{side}_streak"
        if col in gf.columns:
            gf[f"{col}_bin"] = gf[col].apply(
                lambda x: "win3+" if x >= 3 else ("loss3+" if x <= -3 else "other")
                if not pd.isna(x) else np.nan
            )
            feat_bins[f"{col}_bin"] = ["win3+", "loss3+", "other"]

    # Last margin
    for side in ["home", "away"]:
        col = f"{side}_last_margin"
        if col in gf.columns:
            gf[f"{col}_bin"] = gf[col].apply(
                lambda x: "blowout_loss" if x <= -15 else ("blowout_win" if x >= 15 else "normal")
                if not pd.isna(x) else np.nan
            )
            feat_bins[f"{col}_bin"] = ["blowout_loss", "blowout_win", "normal"]

    # Opener total band
    if "pin_open_total" in gf.columns:
        gf["opener_total_band"] = pd.cut(gf["pin_open_total"], bins=[0, 220, 230, 500],
                                          labels=["lt220", "220-230", "gt230"])
        feat_bins["opener_total_band"] = ["lt220", "220-230", "gt230"]

    # Total move
    tm = gf.get("pin_total_move", gf.get("pin_total_move_feat"))
    if tm is not None:
        gf["total_move_band"] = pd.cut(tm, bins=[-50, -2, 2, 50], labels=["le-2", "flat", "ge+2"])
        feat_bins["total_move_band"] = ["le-2", "flat", "ge+2"]

    # Spread move
    if "pin_spread_move_h" in gf.columns:
        gf["spread_move_band"] = pd.cut(gf["pin_spread_move_h"], bins=[-50, -1.5, 1.5, 50],
                                          labels=["le-1.5", "flat", "ge+1.5"])
        feat_bins["spread_move_band"] = ["le-1.5", "flat", "ge+1.5"]

    # Month, weekday
    if "month" in gf.columns:
        gf["month_str"] = gf["month"].astype(int).astype(str)
        feat_bins["month_str"] = [str(m) for m in sorted(gf["month"].dropna().unique().astype(int))]
    if "weekday" in gf.columns:
        gf["weekday_str"] = gf["weekday"].astype(int).astype(str)
        feat_bins["weekday_str"] = [str(w) for w in sorted(gf["weekday"].dropna().unique().astype(int))]

    # --- V2 market-behaviour features ---
    # f1: soft-Pinnacle ML divergence
    if "f1_ml_div_abs" in gf.columns:
        gf["f1_ml_div_flag"] = gf["f1_ml_div_abs"].apply(
            lambda x: "yes" if not pd.isna(x) else "no"
        )
        feat_bins["f1_ml_div_flag"] = ["yes", "no"]
        valid = gf["f1_ml_div_abs"].notna()
        if valid.sum() >= 30:
            gf.loc[valid, "f1_ml_div_band"] = pd.cut(
                gf.loc[valid, "f1_ml_div_abs"],
                bins=[0.02, 0.04, 0.07, 1.0], labels=["small", "medium", "large"],
                include_lowest=True
            )
            feat_bins["f1_ml_div_band"] = ["small", "medium", "large"]

    # f1: soft-Pinnacle spread divergence
    if "f1_spread_divergence" in gf.columns:
        gf["f1_spr_div_flag"] = gf["f1_spread_divergence"].apply(
            lambda x: "yes" if not pd.isna(x) else "no"
        )
        feat_bins["f1_spr_div_flag"] = ["yes", "no"]

    # f2: ML timing share
    if "f2_ml_timing_share" in gf.columns:
        valid = gf["f2_ml_timing_share"].notna()
        if valid.sum() >= 30:
            gf.loc[valid, "f2_ml_timing_band"] = gf.loc[valid, "f2_ml_timing_share"].apply(
                lambda x: "early" if x < 0.3 else ("mixed" if x < 0.7 else "late")
            )
            feat_bins["f2_ml_timing_band"] = ["early", "mixed", "late"]

    # f2: spread timing share
    if "f2_spread_timing_share" in gf.columns:
        valid = gf["f2_spread_timing_share"].notna()
        if valid.sum() >= 30:
            gf.loc[valid, "f2_spr_timing_band"] = gf.loc[valid, "f2_spread_timing_share"].apply(
                lambda x: "early" if x < 0.3 else ("mixed" if x < 0.7 else "late")
            )
            feat_bins["f2_spr_timing_band"] = ["early", "mixed", "late"]

    # f3: divisional flag
    if "f3_divisional" in gf.columns:
        gf["f3_div_flag"] = gf["f3_divisional"].apply(
            lambda x: "yes" if x == 1 else ("no" if x == 0 else np.nan)
        )
        feat_bins["f3_div_flag"] = ["yes", "no"]

    cells = []
    for feat, levels in feat_bins.items():
        for level in levels:
            for side_name, resid_fn, valid_fn in sides:
                mask = (gf[feat] == level) & valid_fn(gf)
                fired = gf[mask].copy()
                if len(fired) == 0:
                    continue
                fired["residual"] = resid_fn(fired)
                fired["cell_side"] = side_name
                cells.append({
                    "cell_id": f"T2_NBA_{feat}_{level}_{side_name}",
                    "sport": "nba", "tier": 2,
                    "feature": feat, "level": level, "side": side_name,
                    "n_fired": len(fired), "data": fired,
                })

    return cells
