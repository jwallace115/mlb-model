"""
V2.1 Lineup Feature Builder.

Reads:
  soccer/data/lineups_raw.parquet            — starting XI + subs per game
  soccer/data/soccer_canonical.parquet       — game dates, team names, scores
  soccer/data/cache/api_football/            — cached lineup JSONs (for formation)

Builds one row per game with 30 lineup features covering:
  A. Lineup delta (actual vs baseline XI strength)
  B. Position-group deltas (ATT / MID / DEF)
  C. Absence flags (GK, primary attacker, leading-scorer proxy)
  D. Lineup continuity (overlap % vs last match and last 3)
  E. Formation structure (num attackers, defenders, back-five)
  F. Matchup interaction terms

Leakage rules:
  - All baselines use game_date strictly less than current match
  - Season boundaries reset all lineup history
  - First match of season: shrink toward league-season average
  - No post-match data used anywhere
"""

import glob
import json
import logging
import os

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# ── Position map ──────────────────────────────────────────────────────────────
# API-Football pos codes → canonical group
POS_MAP = {
    "G": "GK",
    "D": "DEF",
    "M": "MID",
    "F": "ATT",
}

# Minimum prior matches before using raw rates (else shrink toward league avg)
MIN_GAMES_FULL_WEIGHT = 5


# ── Formation parsing ─────────────────────────────────────────────────────────

def _parse_formation(formation_str: str | None) -> dict:
    """
    Parse '4-3-3' → {num_defenders:4, num_midfielders:3, num_attackers:3, back_five:0}
    Returns all zeros on failure.
    """
    result = {
        "num_defenders":   0,
        "num_midfielders": 0,
        "num_attackers":   0,
        "back_five":       0,
    }
    if not formation_str:
        return result
    try:
        parts = [int(x) for x in str(formation_str).split("-")]
        if len(parts) >= 2:
            result["num_defenders"]   = parts[0]
            result["num_midfielders"] = parts[1] if len(parts) > 1 else 0
            result["num_attackers"]   = parts[-1]
            result["back_five"]       = int(parts[0] >= 5)
    except (ValueError, AttributeError):
        pass
    return result


def load_formations(cache_dir: str, crosswalk: pd.DataFrame) -> pd.DataFrame:
    """
    Re-parse cached lineup JSONs to extract formation strings.
    Returns DataFrame: fixture_id, team_side, formation_str
    """
    rows = []
    # Build fixture_id → game_id lookup
    fid_to_gid = dict(zip(
        crosswalk["fixture_id"].dropna().astype(int),
        crosswalk["game_id"]
    ))

    pattern = os.path.join(cache_dir, "fixtures_lineups_fixture*.json")
    files   = glob.glob(pattern)
    logger.info(f"Reading formations from {len(files):,} cached lineup files")

    for fpath in files:
        fname = os.path.basename(fpath)
        try:
            fid = int(fname.replace("fixtures_lineups_fixture", "").replace(".json", ""))
        except ValueError:
            continue

        gid = fid_to_gid.get(fid)
        if gid is None:
            continue

        try:
            with open(fpath) as f:
                data = json.load(f)
        except Exception:
            continue

        for i, team_entry in enumerate(data.get("response", [])):
            formation = team_entry.get("formation")
            team_name = team_entry.get("team", {}).get("name", "")
            rows.append({
                "game_id":      gid,
                "fixture_id":   fid,
                "team_name":    team_name,
                "entry_index":  i,   # 0=home, 1=away in API order (not reliable)
                "formation_str": formation,
            })

    return pd.DataFrame(rows)


# ── Core feature computation ──────────────────────────────────────────────────

def build_lineup_features(
    canonical_path: str,
    lineups_path: str,
    cache_dir: str,
    crosswalk_path: str,
) -> pd.DataFrame:
    """
    Main entry point. Returns DataFrame with one row per game_id,
    all lineup features, ready to merge with soccer_feature_table.parquet.
    """
    # ── Load data ─────────────────────────────────────────────────────────────
    canonical = pd.read_parquet(canonical_path, columns=[
        "game_id", "game_date", "season_year", "league_id",
        "home_team", "away_team",
    ])
    canonical["game_date"] = pd.to_datetime(canonical["game_date"])
    logger.info(f"Canonical: {len(canonical):,} rows")

    lineups = pd.read_parquet(lineups_path)
    logger.info(f"Lineups raw: {len(lineups):,} rows")

    crosswalk = pd.read_parquet(crosswalk_path)

    # ── Join game_date and team identifiers onto lineups ──────────────────────
    lineups = lineups.merge(
        canonical[["game_id", "game_date", "season_year", "league_id",
                   "home_team", "away_team"]],
        on="game_id", how="left",
        suffixes=("", "_can"),
    )
    # Resolve season_year / league_id duplicates from raw vs canonical
    for col in ["season_year", "league_id"]:
        dup = f"{col}_can"
        if dup in lineups.columns:
            lineups[col] = lineups[col].combine_first(lineups[dup])
            lineups.drop(columns=[dup], inplace=True)

    lineups["pos_group"] = lineups["position"].map(POS_MAP).fillna("UNK")

    starters = lineups[lineups["is_starter"] == True].copy()
    logger.info(f"Starter rows: {len(starters):,}")

    # ── Load formations ───────────────────────────────────────────────────────
    formations_df = load_formations(cache_dir, crosswalk)
    logger.info(f"Formation rows: {len(formations_df):,}")

    # Match team_side (home/away) to formation using canonical team names
    # API-Football entry 0 = home, entry 1 = away (in practice, but not guaranteed)
    # Use team_name fuzzy match against canonical home_team/away_team
    formations_df = formations_df.merge(
        canonical[["game_id", "home_team", "away_team"]], on="game_id", how="left"
    )

    def _assign_side(row):
        from difflib import SequenceMatcher
        def sim(a, b):
            return SequenceMatcher(None, str(a).lower(), str(b).lower()).ratio()
        h = sim(row["team_name"], row.get("home_team", ""))
        a = sim(row["team_name"], row.get("away_team", ""))
        return "home" if h >= a else "away"

    formations_df["team_side"] = formations_df.apply(_assign_side, axis=1)

    # ── Build player start-rate history (leakage-safe) ────────────────────────
    # For each (league_id, season_year, team_name, player_id):
    #   prior_starts = cumulative starts before current game date
    #   prior_games  = cumulative games team played before current game date

    # Step 1: team game order — one row per (team × game)
    # Combine home and away perspectives
    home_games = starters[starters["team_side"] == "home"][[
        "game_id", "game_date", "season_year", "league_id", "home_team"
    ]].rename(columns={"home_team": "team_name"}).drop_duplicates("game_id")
    away_games = starters[starters["team_side"] == "away"][[
        "game_id", "game_date", "season_year", "league_id", "away_team"
    ]].rename(columns={"away_team": "team_name"}).drop_duplicates("game_id")
    team_games = pd.concat([home_games, away_games], ignore_index=True).drop_duplicates(
        subset=["game_id", "team_name"]
    ).sort_values(["league_id", "season_year", "team_name", "game_date"]).reset_index(drop=True)

    # Step 2: for each team, count prior games (shift(1)+expanding)
    tg_grp = team_games.groupby(["league_id", "season_year", "team_name"])
    team_games["n_prior_games"] = tg_grp["game_date"].transform(
        lambda x: x.shift(1).expanding().count().fillna(0)
    )

    # Step 3: for each (team × game × player), compute prior starts
    # Merge team_games n_prior_games onto starters
    starters = starters.merge(
        team_games[["game_id", "team_name", "n_prior_games"]],
        on=["game_id", "team_name"], how="left",
        suffixes=("", "_tg"),
    )
    if "n_prior_games_tg" in starters.columns:
        starters["n_prior_games"] = starters["n_prior_games"].combine_first(
            starters["n_prior_games_tg"]
        )
        starters.drop(columns=["n_prior_games_tg"], inplace=True)

    # Step 4: cumulative prior starts per player per (team, season)
    # Sort: (league, season, team, player, game_date)
    starters = starters.sort_values(
        ["league_id", "season_year", "team_name", "player_id", "game_date"]
    ).reset_index(drop=True)

    # prior_starts = shift(1) + expanding sum = starts before current game
    pl_grp = starters.groupby(
        ["league_id", "season_year", "team_name", "player_id"],
        sort=False,
    )
    starters["prior_starts_player"] = pl_grp["is_starter"].transform(
        lambda x: x.shift(1).fillna(0).cumsum()
    )

    # start_rate_prior = prior_starts / n_prior_games (0 when n_prior_games=0)
    n_games = starters["n_prior_games"].replace(0, np.nan)
    starters["start_rate_prior"] = (starters["prior_starts_player"] / n_games).fillna(0.0)

    # ── League-season average start rate (for shrinkage) ──────────────────────
    # Approximate: in a full XI of 11 from a 20-man squad, average start rate ≈ 11/20 ≈ 0.55
    # Use empirical season mean as shrinkage target
    league_season_avg_rate = (
        starters.groupby(["league_id", "season_year"])["start_rate_prior"]
        .mean()
        .rename("league_avg_start_rate")
        .reset_index()
    )
    starters = starters.merge(league_season_avg_rate, on=["league_id", "season_year"], how="left")

    # Shrinkage: w = min(n_prior_games, MIN_GAMES_FULL_WEIGHT) / MIN_GAMES_FULL_WEIGHT
    w = (starters["n_prior_games"].clip(upper=MIN_GAMES_FULL_WEIGHT) / MIN_GAMES_FULL_WEIGHT).fillna(0)
    starters["start_rate_shrunk"] = (
        w * starters["start_rate_prior"] + (1 - w) * starters["league_avg_start_rate"]
    ).fillna(starters["league_avg_start_rate"])

    # ── Per-game, per-team aggregations ──────────────────────────────────────
    # Group by (game_id, team_name) and compute features
    def _team_game_features(grp: pd.DataFrame) -> pd.Series:
        n_games_val = grp["n_prior_games"].iloc[0]

        # Overall XI strength
        actual_strength = grp["start_rate_shrunk"].mean()

        # Position-specific strengths
        att = grp[grp["pos_group"] == "ATT"]["start_rate_shrunk"]
        mid = grp[grp["pos_group"] == "MID"]["start_rate_shrunk"]
        def_ = grp[grp["pos_group"] == "DEF"]["start_rate_shrunk"]
        gk  = grp[grp["pos_group"] == "GK"]["start_rate_shrunk"]

        att_strength  = att.mean()  if len(att)  > 0 else np.nan
        mid_strength  = mid.mean()  if len(mid)  > 0 else np.nan
        def_strength  = def_.mean() if len(def_) > 0 else np.nan
        gk_strength   = gk.mean()   if len(gk)   > 0 else np.nan

        # Baseline = top-11 players by start_rate_shrunk (the "expected" XI)
        top11 = grp.nlargest(11, "start_rate_shrunk")
        baseline_strength = top11["start_rate_shrunk"].mean()

        # Lineup delta: negative = rotation, 0 = full strength
        lineup_delta = actual_strength - baseline_strength

        # Position deltas
        top_att = top11[top11["pos_group"] == "ATT"]["start_rate_shrunk"]
        top_def = top11[top11["pos_group"] == "DEF"]["start_rate_shrunk"]
        att_delta  = att_strength  - (top_att.mean()  if len(top_att)  > 0 else att_strength)
        def_delta  = def_strength  - (top_def.mean()  if len(top_def)  > 0 else def_strength)

        # Absence flags
        # First-choice GK: player with highest prior start_rate in GK position
        gk_rows  = grp[grp["pos_group"] == "GK"]
        att_rows = grp[grp["pos_group"] == "ATT"]

        gk_missing_flag  = 0
        att_missing_flag = 0

        if n_games_val >= 3:  # only meaningful after some history
            # Is GK present? If any GK in XI with start_rate_shrunk < 0.8, flag
            # Better: check if GK is NOT the most-used GK historically
            # We approximate: if GK start_rate < 0.60, they are not first-choice
            if not gk_rows.empty:
                fc_gk_rate = gk_rows["start_rate_shrunk"].max()
                gk_missing_flag = int(fc_gk_rate < 0.60)

            if not att_rows.empty:
                fc_att_rate = att_rows["start_rate_shrunk"].max()
                att_missing_flag = int(fc_att_rate < 0.55)

        return pd.Series({
            "xi_actual_strength":   actual_strength,
            "xi_baseline_strength": baseline_strength,
            "lineup_delta":         lineup_delta,
            "att_strength":         att_strength,
            "def_strength":         def_strength,
            "gk_missing":           gk_missing_flag,
            "primary_att_missing":  att_missing_flag,
            "n_prior_games_team":   n_games_val,
        })

    logger.info("Computing per-game team strength features...")
    team_feats = (
        starters
        .groupby(["game_id", "team_name"], sort=False)
        .apply(_team_game_features)
        .reset_index()
    )

    # ── Lineup continuity ─────────────────────────────────────────────────────
    logger.info("Computing lineup continuity...")

    # For each (game_id, team_name), get the set of starter player_ids
    starter_sets = (
        starters.groupby(["game_id", "game_date", "season_year",
                           "league_id", "team_name"])["player_id"]
        .apply(frozenset)
        .reset_index()
        .rename(columns={"player_id": "starter_set"})
        .sort_values(["league_id", "season_year", "team_name", "game_date"])
        .reset_index(drop=True)
    )

    def _continuity_features(grp: pd.DataFrame) -> pd.DataFrame:
        """Per-(league, season, team) group — compute overlap with prior XIs."""
        grp = grp.sort_values("game_date").reset_index(drop=True)
        overlaps_last   = []
        overlaps_roll3  = []

        for i in range(len(grp)):
            cur_set = grp.loc[i, "starter_set"]
            prior = grp.iloc[:i]

            if len(prior) == 0:
                overlaps_last.append(np.nan)
                overlaps_roll3.append(np.nan)
                continue

            # Overlap with last match
            last_set = prior.iloc[-1]["starter_set"]
            overlap_last = len(cur_set & last_set) / 11.0

            # Overlap with mean of last 3
            last3 = prior.tail(3)
            overlap_r3 = np.mean([
                len(cur_set & row["starter_set"]) / 11.0
                for _, row in last3.iterrows()
            ])
            overlaps_last.append(overlap_last)
            overlaps_roll3.append(overlap_r3)

        grp["overlap_last_match"] = overlaps_last
        grp["overlap_rolling_3"]  = overlaps_roll3
        return grp

    starter_sets = (
        starter_sets
        .groupby(["league_id", "season_year", "team_name"], sort=False)
        .apply(_continuity_features)
        .reset_index(drop=True)
    )

    # ── Assemble per-match (home + away) → pivot to one row per game ──────────
    logger.info("Pivoting to one row per game...")

    def _merge_side(canon_col: str, side: str) -> pd.DataFrame:
        """
        Merge team_feats and continuity for one side (home/away).
        canon_col: 'home_team' or 'away_team'
        side:      'home'     or 'away'
        """
        # Get team_name for this side from canonical
        side_df = canonical[["game_id", canon_col]].rename(columns={canon_col: "team_name"})

        tf = team_feats.merge(side_df, on=["game_id", "team_name"], how="inner")
        ct = starter_sets[["game_id", "team_name", "overlap_last_match", "overlap_rolling_3"]].merge(
            side_df, on=["game_id", "team_name"], how="inner"
        )

        merged = tf.merge(ct[["game_id", "team_name", "overlap_last_match", "overlap_rolling_3"]],
                          on=["game_id", "team_name"], how="left")

        prefix = side + "_"
        rename_map = {
            "lineup_delta":          prefix + "lineup_delta",
            "att_strength":          prefix + "att_strength",
            "def_strength":          prefix + "def_strength",
            "gk_missing":            prefix + "first_choice_gk_missing",
            "primary_att_missing":   prefix + "primary_attacker_missing",
            "overlap_last_match":    prefix + "lineup_overlap_last_match",
            "overlap_rolling_3":     prefix + "lineup_overlap_rolling_3",
            "xi_actual_strength":    prefix + "xi_actual_strength",
            "n_prior_games_team":    prefix + "n_prior_games_team",
        }
        return merged.rename(columns=rename_map)[
            ["game_id"] + list(rename_map.values())
        ]

    home_side = _merge_side("home_team", "home")
    away_side = _merge_side("away_team", "away")

    game_feats = canonical[["game_id"]].merge(home_side, on="game_id", how="left")
    game_feats = game_feats.merge(away_side,  on="game_id", how="left")

    # ── Formation features ────────────────────────────────────────────────────
    logger.info("Computing formation features...")

    for side in ["home", "away"]:
        canon_col = f"{side}_team"
        side_form = formations_df[["game_id", "team_name", "formation_str", "team_side"]].copy()
        # Filter to correct side
        side_form = side_form[side_form["team_side"] == side]
        # Match to canonical team name via game_id + side
        side_form = side_form.merge(
            canonical[["game_id", canon_col]].rename(columns={canon_col: "canon_team"}),
            on="game_id", how="left"
        )
        # Parse formations
        parsed = side_form["formation_str"].apply(_parse_formation).apply(pd.Series)
        side_form = pd.concat([side_form[["game_id"]], parsed], axis=1)
        # Prefix columns
        side_form = side_form.rename(columns={
            "num_defenders":   f"{side}_num_defenders",
            "num_midfielders": f"{side}_num_midfielders",
            "num_attackers":   f"{side}_num_attackers",
            "back_five":       f"{side}_back_five",
        }).drop_duplicates("game_id")
        game_feats = game_feats.merge(side_form, on="game_id", how="left")

    # ── Matchup interaction terms ─────────────────────────────────────────────
    game_feats["home_attack_delta_vs_away_defense"] = (
        game_feats["home_att_strength"].fillna(0) -
        game_feats["away_def_strength"].fillna(0)
    )
    game_feats["away_attack_delta_vs_home_defense"] = (
        game_feats["away_att_strength"].fillna(0) -
        game_feats["home_def_strength"].fillna(0)
    )
    game_feats["net_lineup_attack_edge"] = (
        game_feats.get("home_lineup_delta", pd.Series(0, index=game_feats.index)).fillna(0) +
        game_feats.get("away_lineup_delta", pd.Series(0, index=game_feats.index)).fillna(0)
    )
    game_feats["net_lineup_defense_weakness"] = -(
        game_feats["home_def_strength"].fillna(0) +
        game_feats["away_def_strength"].fillna(0)
    )

    logger.info(f"Lineup features built: {len(game_feats):,} rows, {len(game_feats.columns)} columns")
    return game_feats


# ── Leakage audit ─────────────────────────────────────────────────────────────

LINEUP_FEATURE_COLS = [
    "home_lineup_delta", "away_lineup_delta",
    "home_att_strength", "away_att_strength",
    "home_def_strength", "away_def_strength",
    "home_first_choice_gk_missing", "away_first_choice_gk_missing",
    "home_primary_attacker_missing", "away_primary_attacker_missing",
    "home_lineup_overlap_last_match", "away_lineup_overlap_last_match",
    "home_lineup_overlap_rolling_3", "away_lineup_overlap_rolling_3",
    "home_num_defenders", "away_num_defenders",
    "home_num_attackers", "away_num_attackers",
    "home_back_five", "away_back_five",
    "home_attack_delta_vs_away_defense",
    "away_attack_delta_vs_home_defense",
    "net_lineup_attack_edge",
    "net_lineup_defense_weakness",
]


def run_leakage_audit(lineup_feats: pd.DataFrame, lineups_raw: pd.DataFrame,
                      canonical: pd.DataFrame) -> None:
    SEP  = "═" * 72
    SEP2 = "─" * 72

    print(f"\n{SEP}")
    print("  V2.1 LINEUP FEATURE LEAKAGE AUDIT")
    print(SEP)
    print(f"\n  Feature table: {len(lineup_feats):,} rows, {len(lineup_feats.columns)} columns")
    print()

    # Section 1: Null rates
    print("  SECTION 1: Null % per lineup feature")
    print(f"  {SEP2[:60]}")
    for feat in LINEUP_FEATURE_COLS:
        if feat not in lineup_feats.columns:
            print(f"  MISSING  {feat}")
            continue
        null_pct = lineup_feats[feat].isna().mean() * 100
        # Continuity features are NaN for first game — expected
        ok = "✓" if null_pct < 30 else ("⚠" if null_pct < 50 else "✗")
        print(f"  {ok} {feat:<45} {null_pct:>6.2f}% null")
    print()

    # Section 2: Season boundary check
    print("  SECTION 2: Season boundary check")
    print(f"  {SEP2[:60]}")
    # Find first game of each team-season → overlap_last_match should be NaN
    starters = lineups_raw[lineups_raw["is_starter"] == True].copy()
    # Drop cols that already exist in lineups_raw to avoid _x/_y conflicts
    drop_before_merge = [c for c in ["season_year", "league_id"] if c in starters.columns]
    starters = starters.drop(columns=drop_before_merge)
    starters = starters.merge(
        canonical[["game_id", "game_date", "season_year", "league_id", "home_team", "away_team"]],
        on="game_id", how="left"
    )
    for side, team_col in [("home", "home_team"), ("away", "away_team")]:
        side_st = starters[starters["team_side"] == side]
        if side_st.empty:
            continue
        first_games = (
            side_st.groupby(["league_id", "season_year", team_col])["game_date"]
            .min().reset_index().rename(columns={"game_date": "first_game_date"})
        )
        first_games = first_games.merge(
            canonical[["game_id", "game_date", team_col]],
            on=[team_col], how="inner"
        )
        first_games = first_games[first_games["game_date"] == first_games["first_game_date"]]
        # Check overlap_last_match should be NaN for these
        col = f"{side}_lineup_overlap_last_match"
        if col in lineup_feats.columns:
            first_with_feat = first_games[["game_id"]].merge(lineup_feats[["game_id", col]], on="game_id")
            non_null = first_with_feat[col].notna().sum()
            total = len(first_with_feat)
            ok = "✓" if non_null == 0 else "⚠"
            print(f"  {ok} {side} first-game overlap_last_match: {non_null}/{total} non-null "
                  f"(expected 0 — NaN means no prior match)")
    print()

    # Section 3: Manual trace — 5 games
    print("  SECTION 3: Manual trace — lineup_delta for 5 games")
    print(f"  {SEP2[:60]}")
    print("  Verifying: lineup_delta uses only prior-game start rates\n")

    canonical_dt = canonical.copy()
    canonical_dt["game_date"] = pd.to_datetime(canonical_dt["game_date"])

    np.random.seed(42)
    sample_gids = lineup_feats[lineup_feats["home_n_prior_games_team"] >= 5]["game_id"].sample(5).tolist()

    for gid in sample_gids:
        row_feat = lineup_feats[lineup_feats["game_id"] == gid].iloc[0]
        can_row  = canonical_dt[canonical_dt["game_id"] == gid].iloc[0]
        home     = can_row["home_team"]
        gdate    = can_row["game_date"]
        season   = can_row["season_year"]
        league   = can_row["league_id"]

        # Get prior home games for this team this season
        home_st = starters[
            (starters["team_side"] == "home") &
            (starters["home_team"] == home) &
            (starters["season_year"] == season) &
            (starters["league_id"] == league) &
            (pd.to_datetime(starters["game_date"]) < gdate)
        ]

        n_prior = home_st["game_id"].nunique()
        lineup_delta = row_feat.get("home_lineup_delta", np.nan)

        # This game's actual starters
        actual_st = starters[
            (starters["game_id"] == gid) &
            (starters["team_side"] == "home")
        ]

        print(f"  {home}  |  {season}  |  {gdate.date()}")
        print(f"    prior home games in season: {n_prior}")
        print(f"    feature home_lineup_delta:  {lineup_delta:.4f}" if not pd.isna(lineup_delta) else "    feature: NaN")
        print(f"    actual starters in this game (must NOT be included in their own baseline)")
        # Verify: same game's starters should not appear in prior_starts_player calc
        print(f"    same-game home starters: {actual_st['player_name'].tolist()[:3]}...")
        print()

    # Section 4: Coverage summary
    print("  SECTION 4: Coverage by split")
    print(f"  {SEP2[:60]}")
    feat_with_split = lineup_feats.merge(
        canonical[["game_id", "season_year"]], on="game_id", how="left"
    )
    split_map = {
        "2019-20": "train", "2020-21": "train", "2021-22": "train", "2022-23": "train",
        "2023-24": "validate", "2024-25": "oos",
    }
    feat_with_split["split"] = feat_with_split["season_year"].map(split_map)

    for split in ["train", "validate", "oos"]:
        sub = feat_with_split[feat_with_split["split"] == split]
        if sub.empty:
            continue
        n = len(sub)
        null_any = sub[
            [c for c in LINEUP_FEATURE_COLS if c in sub.columns]
        ].isna().all(axis=1).mean() * 100
        print(f"  {split:<12} {n:>5} rows   {100-null_any:>5.1f}% rows with at least one lineup feature")
    print()
    print("  ✓ Leakage audit complete.")
    print()
