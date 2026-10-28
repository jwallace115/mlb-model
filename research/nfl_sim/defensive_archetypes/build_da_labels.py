#!/usr/bin/env python3
"""DA-1 Item 2: build point-in-time defensive archetype labels.

One row per (season, week, defense). AS-OF RULE: a label for week W uses only games
whose kickoff + 4h < earliest kickoff of week W.

Families: F1 positional funnel, F2 run/pass funnel, F3 explosive allowed, F4 scheme.
Prior-season blend: value_W = (n*current + k*prior) / (n + k), k = 4.
Tercile cutoffs frozen from 2021-23 (scheme: 2023 only).

DA-D6 decision. DA-1 Item 2.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "research" / "nfl_sim" / "defensive_archetypes"
LABELS_DIR = OUT / "labels"
LABELS_DIR.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(OUT))
from team_xwalk import canon

import nflreadpy

BLEND_K = 4  # prior-season weight in games
DISCOVERY_SEASONS = {2021, 2022, 2023}
SCHEME_DISCOVERY = {2023}  # participation man/zone only from 2023
ALL_SEASONS = list(range(2021, 2026))


def _load_pbp(seasons):
    """Load PBP for given seasons."""
    df = nflreadpy.load_pbp(seasons)
    if hasattr(df, "to_pandas"):
        df = df.to_pandas()
    df["_defteam"] = df["defteam"].apply(canon)
    df["_posteam"] = df["posteam"].apply(canon)
    return df


def _load_participation(seasons):
    """Load participation data."""
    frames = []
    for s in seasons:
        try:
            df = nflreadpy.load_participation([s])
            if hasattr(df, "to_pandas"):
                df = df.to_pandas()
            if not df.empty:
                frames.append(df)
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_ftn(seasons):
    """Load FTN charting data."""
    frames = []
    for s in seasons:
        try:
            df = nflreadpy.load_ftn_charting([s])
            if hasattr(df, "to_pandas"):
                df = df.to_pandas()
            if not df.empty:
                frames.append(df)
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_rosters(seasons):
    """Load rosters for receiver position mapping."""
    frames = []
    for s in seasons:
        try:
            r = nflreadpy.load_rosters([s])
            if hasattr(r, "to_pandas"):
                r = r.to_pandas()
            frames.append(r)
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_schedules(seasons):
    """Load schedules for kickoff times."""
    frames = []
    for s in seasons:
        try:
            sc = nflreadpy.load_schedules([s])
            if hasattr(sc, "to_pandas"):
                sc = sc.to_pandas()
            frames.append(sc)
        except Exception:
            pass
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _week_cutoffs(sched):
    """For each (season, week), compute the earliest kickoff.

    Returns {(season, week): earliest_kickoff_utc}.
    """
    cutoffs = {}
    for (s, w), g in sched.groupby(["season", "week"]):
        times = []
        for _, r in g.iterrows():
            try:
                gd = str(r.gameday).strip()
                gt = str(r.gametime).strip()
                if "T" in gt:
                    dt = pd.to_datetime(gt, utc=True)
                else:
                    dt = pd.to_datetime(f"{gd} {gt}").tz_localize("US/Eastern").tz_convert("UTC")
                times.append(dt)
            except Exception:
                pass
        if times:
            cutoffs[(s, w)] = min(times)
    return cutoffs


def _apply_asof(pbp, sched_cutoffs, season, week, disable_asof=False):
    """Filter PBP to games whose kickoff + 4h < earliest kickoff of this week.

    This is the AS-OF RULE: prevents future data from leaking.
    """
    if disable_asof:
        return pbp

    cutoff = sched_cutoffs.get((season, week))
    if cutoff is None:
        return pbp.head(0)  # no cutoff = no data

    # Filter: game_id has the game's actual time embedded; use the schedule
    # We need the actual kickoff time per game. Use the pbp's own game_date + start_time.
    # Simpler: filter by season < current OR (season == current AND week < W),
    # PLUS the previous Monday night (week W-1) which ends by kickoff+4h.
    # The exact rule: kickoff + 4h < cutoff.

    # Get kickoff times per game from the schedule
    valid_games = set()
    for (s, w), earliest in sched_cutoffs.items():
        if s < season:
            # All prior-season games are valid
            for gid in pbp[pbp.season == s]["game_id"].unique():
                valid_games.add(gid)
        elif s == season and w < week:
            # Games from earlier weeks: check kickoff + 4h < cutoff
            week_kick = sched_cutoffs.get((s, w))
            if week_kick and (week_kick + pd.Timedelta(hours=4)) < cutoff:
                for gid in pbp[(pbp.season == s) & (pbp.week == w)]["game_id"].unique():
                    valid_games.add(gid)

    return pbp[pbp["game_id"].isin(valid_games)]


def _blend(current_val, current_n, prior_val, k=BLEND_K):
    """Prior-season blend: (n*current + k*prior) / (n + k)."""
    if prior_val is None or np.isnan(prior_val):
        if current_n == 0:
            return np.nan
        return current_val
    if current_n == 0:
        return prior_val
    return (current_n * current_val + k * prior_val) / (current_n + k)


# ── F1: Positional funnel ──
def _f1_positional_funnel(pbp, rosters):
    """Share of targets allowed to TE/RB/WR, plus receptions/target by position."""
    pass_plays = pbp[(pbp.play_type == "pass") & pbp.receiver_player_id.notna()].copy()
    if pass_plays.empty:
        return {}

    # Map receiver to position via roster
    roster_pos = {}
    for _, r in rosters.iterrows():
        gid = r.get("gsis_id", "")
        pos = r.get("position", "")
        if gid and pos:
            roster_pos[gid] = pos

    pass_plays["_rec_pos"] = pass_plays["receiver_player_id"].map(roster_pos)
    pass_plays["_rec_pos"] = pass_plays["_rec_pos"].fillna("UNK")
    # Simplify: TE, RB (includes FB), WR
    pass_plays["_pos_group"] = pass_plays["_rec_pos"].map(
        lambda p: "TE" if p == "TE" else ("RB" if p in ("RB", "FB", "HB") else
                                           ("WR" if p == "WR" else "OTHER")))

    results = {}
    for def_team, dg in pass_plays.groupby("_defteam"):
        if not def_team:
            continue
        n = len(dg)
        for pos in ["TE", "RB", "WR"]:
            pg = dg[dg._pos_group == pos]
            results.setdefault(def_team, {})
            results[def_team][f"f1_target_share_{pos.lower()}"] = len(pg) / n if n else 0
            completions = pg["complete_pass"].sum() if "complete_pass" in pg.columns else 0
            results[def_team][f"f1_rec_per_target_{pos.lower()}"] = completions / len(pg) if len(pg) else 0
        results[def_team]["f1_n_targets"] = n
    return results


# ── F2: Run/pass funnel ──
def _f2_run_pass_funnel(pbp):
    """Rush EPA/play - pass EPA/play; neutral-situation pass rate faced."""
    results = {}
    for def_team, dg in pbp[pbp._defteam.notna()].groupby("_defteam"):
        # EPA
        rush = dg[dg.play_type == "run"]
        pass_ = dg[dg.play_type == "pass"]
        rush_epa = rush["epa"].mean() if len(rush) and "epa" in rush.columns else 0
        pass_epa = pass_["epa"].mean() if len(pass_) and "epa" in pass_.columns else 0
        results[def_team] = {
            "f2_rush_epa_allowed": rush_epa,
            "f2_pass_epa_allowed": pass_epa,
            "f2_epa_diff": rush_epa - pass_epa,
            "f2_n_plays": len(dg),
        }
        # Neutral situation pass rate faced (score within 7, Q1-3)
        neutral = dg[(dg.score_differential.abs() <= 7) & (dg.qtr.isin([1, 2, 3]))] if "score_differential" in dg.columns else dg
        if len(neutral):
            results[def_team]["f2_neutral_pass_rate"] = (neutral.play_type == "pass").mean()
        else:
            results[def_team]["f2_neutral_pass_rate"] = np.nan
    return results


# ── F3: Explosive allowed ──
def _f3_explosive(pbp):
    """Share of pass plays >= 20 yds and rush plays >= 10 yds."""
    results = {}
    for def_team, dg in pbp[pbp._defteam.notna()].groupby("_defteam"):
        pass_ = dg[dg.play_type == "pass"]
        rush = dg[dg.play_type == "run"]
        n_pass = len(pass_)
        n_rush = len(rush)
        expl_pass = (pass_.yards_gained >= 20).sum() if n_pass and "yards_gained" in pass_.columns else 0
        expl_rush = (rush.yards_gained >= 10).sum() if n_rush and "yards_gained" in rush.columns else 0
        results[def_team] = {
            "f3_explosive_pass_rate": expl_pass / n_pass if n_pass else 0,
            "f3_explosive_rush_rate": expl_rush / n_rush if n_rush else 0,
            "f3_n_pass": n_pass,
            "f3_n_rush": n_rush,
        }
    return results


# ── F4: Scheme (participation 2023+, FTN 2022+) ──
def _derive_defteam(df):
    """Derive defteam from nflverse_game_id and possession_team.

    game_id format: YYYY_WW_AWAY_HOME. The defense is whoever does NOT possess.
    """
    if "defteam" in df.columns and df["defteam"].notna().mean() > 0.5:
        df["_defteam_derived"] = df["defteam"].apply(canon)
        return df
    if "nflverse_game_id" not in df.columns or "possession_team" not in df.columns:
        df["_defteam_derived"] = None
        return df
    parts = df["nflverse_game_id"].str.split("_", expand=True)
    if parts.shape[1] >= 4:
        df["_game_away"] = parts[2]
        df["_game_home"] = parts[3]
        df["_defteam_derived"] = np.where(
            df["possession_team"] == df["_game_home"],
            df["_game_away"].apply(canon),
            df["_game_home"].apply(canon))
    else:
        df["_defteam_derived"] = None
    return df


def _f4_scheme(participation, ftn, season):
    """Man rate, pressure rate, heavy box rate."""
    results = {}

    if not participation.empty and "defense_man_zone_type" in participation.columns:
        participation = _derive_defteam(participation)
        group_col = "_defteam_derived" if "_defteam_derived" in participation.columns else "defteam"
        for def_team, dg in participation.groupby(group_col):
            dt = canon(def_team) if group_col == "defteam" else def_team
            if not dt:
                continue
            labelled = dg[dg.defense_man_zone_type.notna()]
            if len(labelled) < 10:
                continue
            results.setdefault(dt, {})
            results[dt]["f4_man_rate"] = (labelled.defense_man_zone_type.str.contains("man", case=False, na=False)).mean()
            # Pressure rate
            if "number_of_pass_rushers" in dg.columns:
                pr = dg[dg.number_of_pass_rushers.notna()]
                if len(pr):
                    results[dt]["f4_pressure_rate"] = (pr.number_of_pass_rushers >= 5).mean()
                    results[dt]["f4_pressure_source"] = "participation"
            # Heavy box on rush plays
            if "defenders_in_box" in dg.columns:
                box_lab = dg[dg.defenders_in_box.notna()]
                if len(box_lab):
                    results[dt]["f4_box8_rate"] = (box_lab.defenders_in_box >= 8).mean()
            results[dt]["f4_n_plays"] = len(dg)

    # FTN fallback for pressure rate where participation is absent
    if not ftn.empty and "n_blitzers" in ftn.columns:
        ftn = _derive_defteam(ftn)
        gcol = "_defteam_derived" if "_defteam_derived" in ftn.columns else "defteam"
        if gcol in ftn.columns:
            for dt_raw, dg in ftn.groupby(gcol):
                dt = dt_raw if gcol == "_defteam_derived" else canon(dt_raw)
                if not dt:
                    continue
                if dt not in results or "f4_pressure_rate" not in results.get(dt, {}):
                    results.setdefault(dt, {})
                    results[dt]["f4_pressure_rate"] = (dg.n_blitzers >= 1).mean()
                    results[dt]["f4_pressure_source"] = "ftn"
                    if "f4_n_plays" not in results[dt]:
                        results[dt]["f4_n_plays"] = len(dg)

    return results


# ══════════════════════════════════════════════════════════════════════
# Main builder
# ══════════════════════════════════════════════════════════════════════

def _count_games_before_cutoff(sched, season, week, team, cutoffs):
    """Count schedule games for this team in this season with kickoff + 4h < cutoff(week)."""
    cutoff = cutoffs.get((season, week))
    if cutoff is None:
        return 0
    n = 0
    team_games = sched[(sched.season == season) &
                       ((sched.home_team == team) | (sched.away_team == team))]
    for _, g in team_games.iterrows():
        gw = g.get("week", 0)
        if gw >= week:
            continue
        game_kick = cutoffs.get((season, gw))
        if game_kick and (game_kick + pd.Timedelta(hours=4)) < cutoff:
            n += 1
    return n


def build_labels(seasons=None, disable_asof=False):
    """Build all labels for given seasons.

    disable_asof: for testing only — disables the as-of filter. Labels built with
    this flag are NEVER written to disk.
    """
    seasons = seasons or ALL_SEASONS

    print("Loading data...")
    pbp = _load_pbp(list(range(min(seasons) - 1, max(seasons) + 1)))
    rosters = _load_rosters(list(range(min(seasons) - 1, max(seasons) + 1)))
    sched = _load_schedules(list(range(min(seasons) - 1, max(seasons) + 1)))
    participation = _load_participation([s for s in seasons if s >= 2023])
    ftn = _load_ftn([s for s in range(max(min(seasons) - 1, 2022), max(seasons) + 1)])
    cutoffs = _week_cutoffs(sched)

    # Prior season full-season labels
    prior_cache = {}  # (season-1, team) → family dict

    all_rows = []
    for season in seasons:
        print(f"\n=== Season {season} ===")
        weeks = sorted(sched[sched.season == season]["week"].unique())

        for week in weeks:
            # AS-OF: filter pbp
            pbp_asof = _apply_asof(pbp, cutoffs, season, week, disable_asof=disable_asof)
            # Filter to current season only for current-season stats
            pbp_cur = pbp_asof[pbp_asof.season == season]
            # Also include prior season for the blend
            pbp_prior = pbp_asof[pbp_asof.season == season - 1]

            # Participation and FTN filtered similarly
            if not participation.empty and "nflverse_game_id" in participation.columns:
                # Derive season and week from game_id: YYYY_WW_AWAY_HOME
                if "season" not in participation.columns:
                    parts = participation["nflverse_game_id"].str.split("_", expand=True)
                    participation["season"] = parts[0].astype(int)
                    participation["week"] = parts[1].astype(int)
            part_asof = participation[
                (participation.season == season) &
                (participation.week < week)
            ] if not participation.empty and "week" in participation.columns else pd.DataFrame()

            if not ftn.empty and "nflverse_game_id" in ftn.columns:
                if "season" not in ftn.columns:
                    fp = ftn["nflverse_game_id"].str.split("_", expand=True)
                    ftn["season"] = fp[0].astype(int)
                    ftn["week"] = fp[1].astype(int)
            ftn_asof = ftn[
                (ftn.season == season) &
                (ftn.week < week)
            ] if not ftn.empty and "week" in ftn.columns and "season" in ftn.columns else pd.DataFrame()

            # Compute raw family values for current season-to-date
            f1_cur = _f1_positional_funnel(pbp_cur, rosters)
            f2_cur = _f2_run_pass_funnel(pbp_cur)
            f3_cur = _f3_explosive(pbp_cur)
            f4_cur = _f4_scheme(part_asof, ftn_asof, season)

            # Prior season full-season values
            if season - 1 not in prior_cache:
                pbp_prior_full = pbp[pbp.season == season - 1]
                part_prior = participation[participation.season == season - 1] if not participation.empty and "season" in participation.columns else pd.DataFrame()
                ftn_prior = ftn[ftn.season == season - 1] if not ftn.empty and "season" in ftn.columns else pd.DataFrame()
                prior_cache[season - 1] = {
                    "f1": _f1_positional_funnel(pbp_prior_full, rosters),
                    "f2": _f2_run_pass_funnel(pbp_prior_full),
                    "f3": _f3_explosive(pbp_prior_full),
                    "f4": _f4_scheme(part_prior, ftn_prior, season - 1),
                }

            prior = prior_cache.get(season - 1, {})

            # All defenses this season
            all_teams = set()
            for sw in sched[(sched.season == season) & (sched.week <= week)].itertuples():
                all_teams.add(canon(sw.home_team))
                all_teams.add(canon(sw.away_team))
            all_teams.discard(None)

            for team in sorted(all_teams):
                row = {"season": season, "week": week, "defense": team}

                # F1
                cur_f1 = f1_cur.get(team, {})
                pri_f1 = prior.get("f1", {}).get(team, {})
                n_cur = cur_f1.get("f1_n_targets", 0)
                n_pri = pri_f1.get("f1_n_targets", 0)
                for key in ["f1_target_share_te", "f1_target_share_rb", "f1_target_share_wr",
                             "f1_rec_per_target_te", "f1_rec_per_target_rb", "f1_rec_per_target_wr"]:
                    cv = cur_f1.get(key, np.nan)
                    pv = pri_f1.get(key, np.nan) if n_pri >= 8 else np.nan
                    row[key] = _blend(cv, n_cur, pv)

                # F2
                cur_f2 = f2_cur.get(team, {})
                pri_f2 = prior.get("f2", {}).get(team, {})
                n2_cur = cur_f2.get("f2_n_plays", 0)
                n2_pri = pri_f2.get("f2_n_plays", 0)
                for key in ["f2_epa_diff", "f2_neutral_pass_rate", "f2_rush_epa_allowed", "f2_pass_epa_allowed"]:
                    cv = cur_f2.get(key, np.nan)
                    pv = pri_f2.get(key, np.nan) if n2_pri >= 8 else np.nan
                    row[key] = _blend(cv, n2_cur, pv)

                # F3
                cur_f3 = f3_cur.get(team, {})
                pri_f3 = prior.get("f3", {}).get(team, {})
                n3_cur = cur_f3.get("f3_n_pass", 0) + cur_f3.get("f3_n_rush", 0)
                n3_pri = pri_f3.get("f3_n_pass", 0) + pri_f3.get("f3_n_rush", 0)
                for key in ["f3_explosive_pass_rate", "f3_explosive_rush_rate"]:
                    cv = cur_f3.get(key, np.nan)
                    pv = pri_f3.get(key, np.nan) if n3_pri >= 8 else np.nan
                    row[key] = _blend(cv, n3_cur, pv)

                # F4 (scheme: 2023+ participation, 2022+ FTN)
                cur_f4 = f4_cur.get(team, {})
                pri_f4 = prior.get("f4", {}).get(team, {})
                n4_cur = cur_f4.get("f4_n_plays", 0)
                n4_pri = pri_f4.get("f4_n_plays", 0)
                if season >= 2023 or (season >= 2022 and "f4_pressure_rate" in cur_f4):
                    for key in ["f4_man_rate", "f4_pressure_rate", "f4_box8_rate"]:
                        cv = cur_f4.get(key, np.nan)
                        pv = pri_f4.get(key, np.nan) if n4_pri >= 8 else np.nan
                        row[key] = _blend(cv, n4_cur, pv)
                    row["f4_pressure_source"] = cur_f4.get("f4_pressure_source", "none")
                else:
                    row["f4_man_rate"] = np.nan
                    row["f4_pressure_rate"] = np.nan
                    row["f4_box8_rate"] = np.nan
                    row["f4_pressure_source"] = "unlabeled"

                row["n_games_into_label"] = len(pbp_cur[pbp_cur._defteam == team]["game_id"].unique())
                row["uses_prior_blend"] = n_cur == 0 and (n_pri >= 8 or n2_pri >= 8)
                all_rows.append(row)

        print(f"  {season}: {len([r for r in all_rows if r['season'] == season])} rows")

    df = pd.DataFrame(all_rows)

    # ── Tercile cutoffs from discovery seasons only ──
    print("\nComputing tercile cutoffs from discovery seasons...")
    cutoff_data = {}
    TERCILE_COLS = [c for c in df.columns if c.startswith("f1_") or c.startswith("f2_") or c.startswith("f3_") or c.startswith("f4_")]
    TERCILE_COLS = [c for c in TERCILE_COLS if c not in ("f4_pressure_source",)]

    for col in TERCILE_COLS:
        disc = df[df.season.isin(DISCOVERY_SEASONS)]
        if col.startswith("f4_"):
            disc = df[df.season.isin(SCHEME_DISCOVERY)]
        vals = disc[col].dropna()
        if len(vals) < 10:
            continue
        t1 = float(vals.quantile(1/3))
        t2 = float(vals.quantile(2/3))
        cutoff_data[col] = {"t1": round(t1, 6), "t2": round(t2, 6), "n": len(vals)}

    cutoff_json = json.dumps(cutoff_data, indent=1, sort_keys=True)
    cutoff_sha = hashlib.sha256(cutoff_json.encode()).hexdigest()[:16]
    print(f"Tercile cutoffs: {len(cutoff_data)} features, sha={cutoff_sha}")

    # Apply terciles
    for col, cuts in cutoff_data.items():
        tercile_col = col + "_tercile"
        df[tercile_col] = np.where(
            df[col].isna(), np.nan,
            np.where(df[col] <= cuts["t1"], 1,
                     np.where(df[col] <= cuts["t2"], 2, 3)))

    # ── INVARIANT CHECK: n_games_into_label == schedule count ──
    print("\nInvariant check...")
    canon_sched = sched.copy()
    canon_sched["_home"] = canon_sched["home_team"].apply(canon)
    canon_sched["_away"] = canon_sched["away_team"].apply(canon)
    violations = 0
    for _, row in df.iterrows():
        season, week, team = int(row.season), int(row.week), row.defense
        expected = _count_games_before_cutoff(canon_sched, season, week, team, cutoffs)
        actual = int(row.n_games_into_label)
        if actual != expected:
            violations += 1
            if violations <= 5:
                print(f"  VIOLATION: {season} {team} wk{week}: expected {expected}, got {actual}")
    if violations:
        msg = f"HALT: {violations} n_games_into_label violations"
        if not disable_asof:
            raise SystemExit(msg)
        else:
            print(f"  WARNING (as-of disabled): {msg}")

    # ── WRITE GUARD: never write when as-of is disabled ──
    if disable_asof:
        print("  as-of disabled — NOT writing files")
        return df, cutoff_data, cutoff_sha

    # Write tercile cutoffs
    cutoff_path = LABELS_DIR / "tercile_cutoffs_v1.json"
    cutoff_path.write_text(cutoff_json + "\n")

    # Save per-season
    for season in seasons:
        sdf = df[df.season == season]
        path = LABELS_DIR / f"da_labels_{season}.parquet"
        sdf.to_parquet(path, index=False)
        print(f"  {season}: {len(sdf)} rows → {path.name}")

    return df, cutoff_data, cutoff_sha


if __name__ == "__main__":
    df, cuts, sha = build_labels()
    print(f"\nTotal: {len(df)} rows, {len(cuts)} tercile features, sha={sha}")
