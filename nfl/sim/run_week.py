#!/usr/bin/env python3
"""
Phase 4B: Weekly NFL sim runner. Idempotent, re-runnable as lines move.

Usage: python3 nfl/sim/run_week.py [--week N] [--n-sims 10000]

DETECTS the upcoming week from the nflverse schedule (first regular-season week
with unplayed games). --week overrides.
"""

import sys, os, time, json, gc, shutil
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
from nfl.sim.seed_util import stable_seed
from nfl.sim.names import (FULL_TO_ABBR, load_roster, _build_roster_lookup,
                           resolve_player, is_player_name)
from nfl.sim.calibration import load_calibration
from nfl.sim.anchor import run_anchored_chunked
from nfl.sim.pricer import price_game, sgp_probability_raked

SEASON = 2026
OUT_BASE = ROOT / "nfl" / "data" / "sim" / "outputs"
J_INV = np.array([[0.07450484, 0.10168527], [-0.08895527, 0.1277827]])

TEAM_MAP = FULL_TO_ABBR
TEAM_MAP_INV = {v: k for k, v in TEAM_MAP.items()}

# D16 trust tiers
TIER_TRUSTED = {"receptions_WR", "anytime_td_WR"}
TIER_TRUSTED_FLAGGED = {"receptions_TE", "receptions_RB"}
TIER_WATCH = {"rush_attempts_RB"}


def detect_week(override=None):
    """D68: detect current week from schedule (not PBP alone).

    Uses the nflverse schedule which lists ALL games including unplayed.
    A game is complete if it appears in PBP with a final state (any row
    exists for that game_id), not a score threshold. This prevents:
    - advancing past a week once TNF is in PBP but Sunday games are not
    - treating a shutout (home_score==0) as incomplete
    """
    if override is not None:
        print(f"Week override: {override}")
        return override, pd.DataFrame(), set()

    # Load schedule from nflverse
    try:
        import nflreadpy
        sched = nflreadpy.load_schedules([SEASON]).to_pandas()
    except Exception:
        sched = pd.DataFrame()

    # Load PBP for completion check
    pbp_path = ROOT / "nfl" / "data" / "pbp" / f"pbp_{SEASON}.parquet"
    pbp_game_ids = set()
    if pbp_path.exists():
        pbp = pd.read_parquet(pbp_path, columns=["game_id"])
        pbp_game_ids = set(pbp["game_id"].unique())

    if sched.empty:
        # Fallback to PBP-only if schedule unavailable
        if not pbp_path.exists():
            raise FileNotFoundError(f"No PBP or schedule for {SEASON}")
        df = pd.read_parquet(pbp_path, columns=["game_id", "season", "week",
                                                 "home_team", "away_team"])
        games = df.drop_duplicates("game_id")
        for w in sorted(games["week"].unique()):
            wk = games[games["week"] == w]
            incomplete = wk[~wk["game_id"].isin(pbp_game_ids)]
            if len(incomplete) > 0:
                return w, wk, pbp_game_ids
        return int(games["week"].max()) + 1, pd.DataFrame(), pbp_game_ids

    # Use schedule: find first week with incomplete games
    sched = sched[sched["game_type"] == "REG"].copy()
    for w in sorted(sched["week"].unique()):
        wk_sched = sched[sched["week"] == w]
        # A game is complete if its game_id appears in PBP
        wk_gids = set(wk_sched["game_id"]) if "game_id" in wk_sched.columns else set()
        incomplete = wk_gids - pbp_game_ids
        if len(incomplete) > 0:
            return int(w), wk_sched, pbp_game_ids
    return int(sched["week"].max()) + 1, pd.DataFrame(), pbp_game_ids


def get_week_teams_from_schedule(season, week):
    """Get teams playing in a specific week from nflverse schedule."""
    try:
        import nflreadpy
        sched = nflreadpy.load_schedules([season]).to_pandas()
        wk = sched[sched["week"] == week]
        if len(wk) > 0:
            teams = set(wk["home_team"]) | set(wk["away_team"])
            matchups = set()
            for _, g in wk.iterrows():
                matchups.add((g["away_team"], g["home_team"]))
            return teams, matchups
    except Exception:
        pass
    return set(), set()


def get_lines_from_history():
    lh_dir = ROOT / "data" / "odds_archive" / "nfl" / "line_history" / f"season={SEASON}"
    if not lh_dir.exists():
        return {}
    files = sorted(lh_dir.glob("*.parquet"))
    if not files:
        return {}
    df = pd.read_parquet(files[-1])
    lines = {}
    for (home_full, away_full), gdf in df.groupby(["home_team", "away_team"]):
        home = TEAM_MAP.get(home_full, home_full)
        away = TEAM_MAP.get(away_full, away_full)
        hr = gdf[gdf["bookmaker"].str.contains("hardrock", case=False, na=False)]
        if hr.empty:
            hr = gdf
        spreads = hr[hr["market"] == "spreads"]
        home_sp = spreads[spreads["outcome_name"].apply(
            lambda x: home_full.split()[-1] in str(x) if x else False)]
        spread = -float(home_sp["point"].iloc[0]) if not home_sp.empty else None
        totals = hr[hr["market"] == "totals"]
        over = totals[totals["outcome_name"] == "Over"]
        total = float(over["point"].iloc[0]) if not over.empty else None
        if spread is not None and total is not None:
            source = "hardrockbet_fl" if "hardrock" in str(hr["bookmaker"].iloc[0]).lower() else "consensus"
            lines[f"{away}@{home}"] = {
                "home": home, "away": away, "spread": spread, "total": total,
                "source": source,
            }
    return lines


def count_team_completed_games(season):
    """Count completed games per team in the season."""
    pbp_path = ROOT / "nfl" / "data" / "pbp" / f"pbp_{season}.parquet"
    if not pbp_path.exists():
        return {}
    df = pd.read_parquet(pbp_path, columns=["game_id", "home_team", "away_team",
                                             "home_score"])
    games = df.drop_duplicates("game_id")
    completed = games[games["home_score"].notna() & (games["home_score"] > 0)]
    counts = {}
    for _, g in completed.iterrows():
        counts[g["home_team"]] = counts.get(g["home_team"], 0) + 1
        counts[g["away_team"]] = counts.get(g["away_team"], 0) + 1
    return counts


def _run_chunks(home, away, season, week, chunk_size, n_chunks, base_seed,
                dh, da, **kw):
    """Run n_chunks simulations and pool results."""
    all_td = []
    all_pdf = []
    for ci in range(n_chunks):
        seed = (base_seed + ci * 7919) % (2**31)
        result = simulate_game(
            home, away, season, week, n_sims=chunk_size, seed=seed,
            epa_home_offset=dh, epa_away_offset=da, **kw)
        if isinstance(result, tuple):
            td, pdf = result
        else:
            td, pdf = result, None
        if pdf is not None and ci > 0:
            pdf = pdf.copy()
            pdf["sim_id"] = pdf["sim_id"] + ci * chunk_size
        td = td.copy()
        td["sim_id"] = td.index + ci * chunk_size
        all_td.append(td)
        if pdf is not None:
            all_pdf.append(pdf)
        del result
    pooled_td = pd.concat(all_td, ignore_index=True)
    pooled_pdf = pd.concat(all_pdf, ignore_index=True) if all_pdf else None
    del all_td, all_pdf
    margin = (pooled_td["home_score"] - pooled_td["away_score"]).values.astype(float)
    total_arr = (pooled_td["home_score"] + pooled_td["away_score"]).values.astype(float)
    return pooled_td, pooled_pdf, margin.mean(), total_arr.mean(), \
           margin.std() / np.sqrt(len(margin)), total_arr.std() / np.sqrt(len(total_arr))


def run_chunked_game(home, away, season, week, spread, total, n_sims,
                     chunk_size=2000, anchoring_log=None, **kw):
    """Run anchored sims in chunks with damped Newton.

    Fixed J_INV (from calibration) with step-size damping. Steps whose
    predicted move exceeds 6 pts of margin or total are halved.
    Up to 8 iterations; convergence at |market - mean| < 2*SE on both.
    Common random numbers: same seed set across all iterations.
    """
    base_seed = stable_seed((home, away, season, week, 42))
    n_chunks = max(1, n_sims // chunk_size)
    game_key = f"{away}@{home}"
    # J matrix for damping prediction
    J_FWD = np.array([[6.88, -5.48], [4.79, 4.01]])

    dh, da = 0.0, 0.0
    raw_m = raw_t = None
    best_err = float("inf")
    best_state = None

    for it in range(8):
        pooled_td, pooled_pdf, m, t, se_m, se_t = _run_chunks(
            home, away, season, week, chunk_size, n_chunks, base_seed,
            dh, da, **kw)
        if it == 0:
            raw_m, raw_t = m, t
        me = spread - m
        te = total - t
        err_norm = abs(me) + abs(te)

        if anchoring_log is not None:
            anchoring_log.append({
                "game": game_key, "iter": it, "dh": dh, "da": da,
                "margin": m, "total": t, "se_m": se_m, "se_t": se_t,
                "err_m": me, "err_t": te,
                "converged": abs(me) < 2 * se_m and abs(te) < 2 * se_t,
            })

        # Track best iteration
        if err_norm < best_err:
            best_err = err_norm
            best_state = (pooled_td, pooled_pdf, dh, da, it + 1, m, t)

        if abs(me) < 2 * se_m and abs(te) < 2 * se_t:
            return pooled_td, pooled_pdf, dh, da, it + 1, True, raw_m, raw_t, m, t

        err = np.array([me, te])
        step = J_INV @ err

        # Damp: halve step until predicted move is within 6 pts on each channel
        for _ in range(5):
            pred = J_FWD @ step
            if abs(pred[0]) <= 6 and abs(pred[1]) <= 6:
                break
            step = step * 0.5

        dh += step[0]
        da += step[1]
        if it < 7:
            del pooled_td, pooled_pdf
            gc.collect()

    # Return best iteration if final is worse
    b_td, b_pdf, b_dh, b_da, b_it, b_m, b_t = best_state
    if abs(spread - b_m) + abs(total - b_t) < err_norm:
        return b_td, b_pdf, b_dh, b_da, b_it, False, raw_m, raw_t, b_m, b_t
    return pooled_td, pooled_pdf, dh, da, 8, False, raw_m, raw_t, m, t


def load_props_for_game(home_full, away_full, season, week):
    """D69: Load Hard Rock props, selecting by snapshot_tag precedence.

    Tag precedence: close > mid > open. Within a tag, latest pull_timestamp
    wins. Returns (DataFrame, chosen_tag, chosen_timestamp). Raises on
    unknown snapshot_tag rather than falling through.
    """
    _TAG_PRECEDENCE = {"close": 3, "mid": 2, "open": 1}

    props_dir = ROOT / "data" / "odds_archive" / "nfl" / "props" / f"season={season}"
    if not props_dir.exists():
        return pd.DataFrame(), None, None
    frames = []
    for root, dirs, files in os.walk(props_dir):
        for f in files:
            if f.endswith('.parquet'):
                try:
                    frames.append(pd.read_parquet(os.path.join(root, f)))
                except Exception:
                    pass
    if not frames:
        return pd.DataFrame(), None, None
    df = pd.concat(frames, ignore_index=True)
    game_df = df[(df["home_team"] == home_full) & (df["away_team"] == away_full)]
    if game_df.empty:
        return pd.DataFrame(), None, None

    # D69: select by snapshot_tag precedence
    if "snapshot_tag" in game_df.columns and game_df["snapshot_tag"].notna().any():
        # Validate tags
        known_tags = game_df["snapshot_tag"].dropna().unique()
        for tag in known_tags:
            if tag not in _TAG_PRECEDENCE:
                raise ValueError(f"Unknown snapshot_tag '{tag}' in props archive")
        # Pick highest-precedence tag present
        best_tag = max(known_tags, key=lambda t: _TAG_PRECEDENCE[t])
        game_df = game_df[game_df["snapshot_tag"] == best_tag]
        # Within that tag, latest pull_timestamp
        game_df = game_df.sort_values("pull_timestamp", ascending=False)
        chosen_ts = game_df["pull_timestamp"].iloc[0] if len(game_df) > 0 else None
        return game_df, best_tag, chosen_ts

    # Fallback: no snapshot_tag column (old data) — use latest pull_batch
    latest_batch = sorted(game_df["pull_batch"].unique())[-1]
    game_df = game_df[game_df["pull_batch"] == latest_batch]
    chosen_ts = game_df["pull_timestamp"].iloc[0] if len(game_df) > 0 else None
    return game_df, None, chosen_ts


def _check_calibration_stamp():
    """D70: Metadata gate — compare calibration stamp against running state.
    Returns (ok, mismatches_list). On mismatch, sim prices are suppressed."""
    import hashlib, subprocess
    cal_path = ROOT / "nfl" / "sim" / "calibration_v1.json"
    if not cal_path.exists():
        return False, ["calibration_v1.json not found"]

    with open(cal_path) as f:
        cal = json.load(f)

    mismatches = []

    # Engine commit
    try:
        head = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                        cwd=ROOT, text=True).strip()
    except Exception:
        head = "unknown"
    cal_commit = cal.get("engine_commit", "")
    if cal_commit and head != cal_commit:
        mismatches.append(f"engine_commit: cal={cal_commit}, HEAD={head}")

    # Usage file sha256
    usage_path = ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet"
    if usage_path.exists():
        usage_sha = hashlib.sha256(usage_path.read_bytes()).hexdigest()[:16]
        cal_sha = cal.get("usage_file_sha256", "")
        if cal_sha and usage_sha != cal_sha:
            mismatches.append(f"usage_sha: cal={cal_sha}, disk={usage_sha}")

    return len(mismatches) == 0, mismatches


def build_board(week, game_results, lines_used, team_game_counts, roster,
                roster_lookups, pull_ts_str):
    """Build board, write picks_log.parquet and parlay_board.md."""
    out_dir = OUT_BASE / f"week={SEASON}_{week:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    cal_maps = load_calibration()
    generated_utc = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')

    # D70: Metadata gate
    stamp_ok, stamp_mismatches = _check_calibration_stamp()
    if not stamp_ok:
        print(f"CALIBRATION STAMP MISMATCH — sim prices suppressed:")
        for mm in stamp_mismatches:
            print(f"  {mm}")
    sim_pricing_enabled = stamp_ok

    def calibrate(raw_p, cal_family_name):
        if cal_family_name in cal_maps:
            return float(np.interp(raw_p,
                                   cal_maps[cal_family_name]["x"],
                                   cal_maps[cal_family_name]["y"]))
        return raw_p

    board_lines = []
    board_lines.append(f"# NFL Week {week} ({SEASON}) Parlay Board")
    board_lines.append(f"\nGenerated: {generated_utc}")
    if pull_ts_str:
        board_lines.append(f"Props prices as of: {pull_ts_str}")
    if not sim_pricing_enabled:
        board_lines.append(f"\n**SIM PRICES SUPPRESSED** — calibration stamp mismatch:")
        for mm in stamp_mismatches:
            board_lines.append(f"  {mm}")
    board_lines.append("")

    all_legs = []  # for picks_log
    layer_log = []  # D71: per-leg layer logging

    MARKET_KEY_MAP = {
        'player_receptions': 'receptions',
        'player_receptions_alternate': 'receptions',
        'player_reception_yds': 'reception_yds',
        'player_reception_yds_alternate': 'reception_yds',
        'player_rush_attempts': 'rush_attempts',
        'player_rush_attempts_alternate': 'rush_attempts',
        'player_rush_yds': 'rush_yds',
        'player_rush_yds_alternate': 'rush_yds',
        'player_anytime_td': 'anytime_td',
    }

    for gr in game_results:
        home = gr["home"]
        away = gr["away"]
        td = gr["team_df"]
        pdf = gr.get("player_df")
        spread = gr["spread"]
        total_line = gr["total"]
        converged = gr["converged"]
        home_full = TEAM_MAP_INV.get(home, home)
        away_full = TEAM_MAP_INV.get(away, away)

        margin = (td["home_score"] - td["away_score"]).values.astype(float)
        total_arr = (td["home_score"] + td["away_score"]).values.astype(float)
        N = len(td)

        # Stale-input flag
        home_games = team_game_counts.get(home, 0)
        away_games = team_game_counts.get(away, 0)
        home_stale = home_games < 2
        away_stale = away_games < 2

        flag = ""
        if not converged:
            flag += " [NOT ANCHORED]"
        board_lines.append(f"## {away} @ {home}{flag}")
        board_lines.append(f"Hard Rock: spread {spread:+.1f} / total {total_line:.1f} ({gr['source']})")
        board_lines.append(f"Anchored: margin {margin.mean():.1f} / total {total_arr.mean():.1f}")
        board_lines.append("")

        # D69: Load props with tag precedence
        props, props_tag, props_chosen_ts = load_props_for_game(home_full, away_full, SEASON, week)
        props_pull_batch = None
        props_pull_ts = None
        if len(props) > 0:
            props_pull_batch = props["pull_batch"].iloc[0]
            props_pull_ts = str(props_chosen_ts) if props_chosen_ts else str(props["pull_timestamp"].iloc[0])

        # Resolve props to player_ids
        by_team, by_fi, by_league = roster_lookups
        props_by_pid = {}
        if len(props) > 0:
            for _, pr in props.iterrows():
                if not is_player_name(pr["player_name"]):
                    continue
                teams = [home, away]
                pid, method = resolve_player(pr["player_name"], SEASON, week,
                                             teams, by_team, by_fi, by_league)
                if not pid:
                    continue
                family = MARKET_KEY_MAP.get(pr["market_key"])
                if not family:
                    continue
                key = (pid, family, pr["line"])
                props_by_pid[key] = {
                    "over_price": pr.get("over_price"),
                    "under_price": pr.get("under_price"),
                    "implied_over": pr.get("implied_over"),
                    "implied_under": pr.get("implied_under"),
                    "pull_batch": pr.get("pull_batch"),
                    "pull_timestamp": pr.get("pull_timestamp"),
                }

        # D58: Load open snapshot for MOVED-AGAINST flag
        open_snapshot = None  # {(player_name, family, line): implied_p}
        if len(props) > 0:
            # Look for snapshot_tag == "open" in the props archive
            props_dir = ROOT / "data" / "odds_archive" / "nfl" / "props"
            open_frames = []
            for f in sorted(props_dir.rglob(f"season={SEASON}/**/*.parquet")):
                if "raw_live" in str(f):
                    continue
                try:
                    odf = pd.read_parquet(f)
                    if "snapshot_tag" in odf.columns:
                        opens = odf[(odf["snapshot_tag"] == "open") &
                                    (odf["bookmaker"] == "hardrockbet_fl") &
                                    (odf["home_team"] == home_full)]
                        if len(opens) > 0:
                            open_frames.append(opens)
                except Exception:
                    pass
            if open_frames:
                odf = pd.concat(open_frames, ignore_index=True)
                open_snapshot = {}
                for _, r in odf.iterrows():
                    fam = MARKET_KEY_MAP.get(r.get("market_key"))
                    if fam and r.get("player_name"):
                        # Resolve name to match picks
                        pid_o, _ = resolve_player(r["player_name"], SEASON, week,
                                                   [home, away], by_team, by_fi, by_league)
                        if pid_o:
                            bp = props_by_pid.get((pid_o, fam, r.get("line")))
                            if bp:
                                # Store the open implied for the over side
                                imp_over_open = r.get("implied_over")
                                if pd.notna(imp_over_open):
                                    open_snapshot[(r["player_name"], fam, r.get("line"))] = imp_over_open

        # Player props
        if pdf is not None and len(pdf) > 0:
            pmeans = pdf.groupby(["player_id", "player_name", "position", "team"]).agg(
                mean_tgt=("targets", "mean"),
                mean_car=("carries", "mean"),
            ).reset_index()

            board_lines.append("### Player props")
            board_lines.append("")
            board_lines.append("| Player | Pos | Prop | Line | Sim P | Cal P | Book | Edge | Tier |")
            board_lines.append("|--------|-----|------|------|-------|-------|------|------|------|")

            for team in [home, away]:
                tp = pmeans[pmeans["team"] == team]
                top_tgt = tp.nlargest(6, "mean_tgt")
                top_car = tp[(tp["position"] != "QB")].nlargest(2, "mean_car")
                selected_pids = set(top_tgt["player_id"]) | set(top_car["player_id"])

                for pid in selected_pids:
                    pr = tp[tp["player_id"] == pid].iloc[0]
                    pname = pr["player_name"]
                    pos = pr["position"]
                    psims = pdf[pdf["player_id"] == pid]
                    stats = pd.DataFrame({"sim_id": np.arange(N)}).merge(
                        psims[["sim_id", "receptions", "rec_yds", "rush_yds",
                               "carries", "anytime_td"]],
                        on="sim_id", how="left").fillna(0)

                    stale_flag = " [PRIOR-ONLY SHARES]" if (team == home and home_stale) or (team == away and away_stale) else ""

                    def _add_leg(family, side, line, sim_p, cal_fam, pos):
                        cal_p = calibrate(sim_p, cal_fam)
                        tier_key = f"{family}_{pos}"
                        if tier_key in TIER_TRUSTED:
                            tier = "TRUSTED"
                        elif tier_key in TIER_TRUSTED_FLAGGED:
                            tier = "TRUSTED-FLAGGED"
                            if pos == "TE":
                                tier += " [TE]"
                            elif pos == "RB":
                                tier += " [RB tail]"
                        elif tier_key in TIER_WATCH:
                            tier = "WATCH [yardage-family calibration not passed]"
                        else:
                            tier = "UNTRUSTED"

                        book_key = (pid, family, line)
                        bp = props_by_pid.get(book_key, {})
                        book_price = bp.get("over_price") if side == "over" else bp.get("under_price")
                        imp_o = bp.get("implied_over")
                        imp_u = bp.get("implied_under")
                        one_sided = False
                        if pd.notna(imp_o) and pd.notna(imp_u) and (imp_o + imp_u) > 0:
                            total_imp = imp_o + imp_u
                            book_implied = (imp_o / total_imp) if side == "over" else (imp_u / total_imp)
                        elif pd.notna(imp_o) and side == "over":
                            book_implied = imp_o
                            one_sided = True
                        elif pd.notna(imp_u) and side == "under":
                            book_implied = imp_u
                            one_sided = True
                        else:
                            book_implied = np.nan
                            one_sided = True

                        # BOOK-MORE-CONFIDENT filter
                        status = "unbet"
                        if pd.notna(book_implied) and book_implied > cal_p + 0.10:
                            status = "BOOK-MORE-CONFIDENT"

                        # A7: rankable = Hard Rock price exists AND anchoring converged
                        has_book = pd.notna(book_price)
                        rankable = has_book and converged

                        # D58: MOVED-AGAINST flag (pre-registered)
                        moved_against = False
                        if has_book and open_snapshot is not None:
                            open_key = (pname, family, line)
                            open_imp = open_snapshot.get(open_key)
                            if open_imp is not None and pd.notna(book_implied):
                                # For over: moved against if market implied_over
                                # went UP (less value for the over bettor)
                                if side == "over":
                                    moved_against = book_implied > open_imp
                                else:
                                    moved_against = book_implied > open_imp

                        leg = {
                            "season": SEASON, "week": week,
                            "game_id": f"{away}@{home}",
                            "home": home, "away": away,
                            "player_id": pid, "player_name": pname,
                            "position": pos, "family": family,
                            "line": line, "side": side,
                            "sim_p": round(sim_p, 4), "cal_p": round(cal_p, 4),
                            "tier": tier,
                            "book_price": book_price if pd.notna(book_price) else None,
                            "book_implied": round(book_implied, 4) if pd.notna(book_implied) else None,
                            "one_sided": one_sided,
                            "pull_batch": props_pull_batch,
                            "pull_timestamp": props_pull_ts,
                            "board_generated_utc": generated_utc,
                            "status": status,
                            "rankable": rankable,
                            "moved_against": moved_against,
                        }
                        all_legs.append(leg)

                        # D71: layer log row
                        layer_log.append({
                            "season": SEASON, "week": week,
                            "game_id": f"{away}@{home}",
                            "player_id": pid, "player_name": pname,
                            "position": pos, "family": family,
                            "line": line, "side": side,
                            "sim_p_raw": round(sim_p, 4),
                            "sim_p_calibrated": round(cal_p, 4),
                            "book_price": book_price if pd.notna(book_price) else None,
                            "book_implied": round(book_implied, 4) if pd.notna(book_implied) else None,
                            "moved_against": moved_against,
                            "snapshot_tag": props_tag,
                            "snapshot_timestamp": props_pull_ts,
                            "tier": tier,
                            "status": status,
                            "rankable": rankable,
                            "sim_pricing_enabled": sim_pricing_enabled,
                            "board_generated_utc": generated_utc,
                        })
                        return leg

                    # Reception props
                    if pos in ("WR", "TE", "RB"):
                        for k in [2, 3, 4, 5, 6, 7]:
                            sim_p = float((stats["receptions"] >= k).mean())
                            if sim_p < 0.05 or sim_p > 0.95:
                                continue
                            leg = _add_leg("receptions", "over", k - 0.5, sim_p,
                                          f"prop_rec_{pos}", pos)
                            if leg["tier"].startswith("TRUSTED") or leg["tier"].startswith("WATCH"):
                                book_str = f"{int(leg['book_price']):+d}" if leg['book_price'] else "no_price"
                                edge_str = f"{(leg['cal_p'] - leg['book_implied']):+.3f}" if leg['book_implied'] else "-"
                                tier_short = leg['tier'].split('[')[0].strip()
                                board_lines.append(
                                    f"| {pname[:18]:18s}{stale_flag} | {pos} | rec >= {k} "
                                    f"| {k-0.5:.1f} | {sim_p:.3f} | {leg['cal_p']:.3f} "
                                    f"| {book_str} | {edge_str} | {tier_short} |")

                    # Anytime TD (WR only for trusted)
                    if pos in ("WR", "RB", "TE"):
                        atd_p = float((stats["anytime_td"] >= 1).mean())
                        if 0.05 < atd_p < 0.95:
                            leg = _add_leg("anytime_td", "over", 0.5, atd_p,
                                          f"prop_atd_{pos}", pos)
                            if pos == "WR" and leg["tier"].startswith("TRUSTED"):
                                book_str = f"{int(leg['book_price']):+d}" if leg['book_price'] else "no_price"
                                edge_str = f"{(leg['cal_p'] - leg['book_implied']):+.3f}" if leg['book_implied'] else "-"
                                board_lines.append(
                                    f"| {pname[:18]:18s}{stale_flag} | {pos} | anytime TD "
                                    f"| 0.5 | {atd_p:.3f} | {leg['cal_p']:.3f} "
                                    f"| {book_str} | {edge_str} | TRUSTED |")

                    # Rush attempts (WATCH tier)
                    if pos == "RB":
                        for k in [5, 10, 15, 20]:
                            sim_p = float((stats["carries"] >= k).mean())
                            if sim_p < 0.05 or sim_p > 0.95:
                                continue
                            _add_leg("rush_attempts", "over", k - 0.5, sim_p,
                                    f"prop_rush_att_{pos}", pos)

            board_lines.append("")

        # Game markets
        board_lines.append("### Game markets")
        board_lines.append("")
        p_hw = (margin > 0).mean()
        p_hc = (margin - spread > 0).mean()
        p_ov = (total_arr > total_line).mean()
        board_lines.append(f"P(home win) = {p_hw:.3f} | P(home cover) = {p_hc:.3f} | P(over) = {p_ov:.3f}")
        board_lines.append("")
        p_m3 = (np.abs(margin) == 3).mean()
        if p_m3 < 0.10:
            board_lines.append(f"**KEY-NUMBER FLAG**: P(|margin|=3) = {p_m3*100:.1f}% (actual ~14.5%). "
                             f"Alt spreads at +/-3 and +/-6 UNRELIABLE.")
        board_lines.append("")
        board_lines.append("---")
        board_lines.append("")

    # A7: Cross-game top-20 — only rankable legs (Hard Rock price + converged)
    trusted_legs = [l for l in all_legs
                    if l["tier"].startswith("TRUSTED")
                    and l["status"] != "BOOK-MORE-CONFIDENT"
                    and l["side"] == "over"
                    and l.get("rankable", False)]
    not_rankable = [l for l in all_legs
                    if l["tier"].startswith("TRUSTED")
                    and l["side"] == "over"
                    and not l.get("rankable", False)]
    if not_rankable:
        board_lines.append(f"## Not rankable ({len(not_rankable)} legs: no Hard Rock price or not converged)")
        board_lines.append("")
    if trusted_legs:
        board_lines.append("## Cross-game top 20 (trusted, over side, not BOOK-MORE-CONFIDENT)")
        board_lines.append("")
        board_lines.append("| Game | Player | Prop | Cal P | Book | Edge |")
        board_lines.append("|------|--------|------|-------|------|------|")
        sorted_legs = sorted(trusted_legs, key=lambda x: -(x["cal_p"] or 0))
        for leg in sorted_legs[:20]:
            book_str = f"{int(leg['book_price']):+d}" if leg['book_price'] else "no_price"
            edge_str = f"{(leg['cal_p'] - leg['book_implied']):+.3f}" if leg['book_implied'] else "-"
            board_lines.append(
                f"| {leg['game_id']:15s} | {leg['player_name'][:15]:15s} "
                f"| {leg['family'][:10]:10s} {leg['line']:.1f} "
                f"| {leg['cal_p']:.3f} | {book_str} | {edge_str} |")

    board_text = "\n".join(board_lines)

    # Write board
    with open(out_dir / "parlay_board.md", "w") as f:
        f.write(board_text)
    print(f"Board written to {out_dir / 'parlay_board.md'}")

    # Write picks_log.parquet
    if all_legs:
        picks_df = pd.DataFrame(all_legs)
        log_path = out_dir / "picks_log.parquet"
        if log_path.exists():
            prev_path = out_dir / "picks_log_prev.parquet"
            shutil.copy2(log_path, prev_path)
        picks_df.to_parquet(log_path, index=False)
        print(f"picks_log: {len(picks_df)} legs -> {log_path}")

        n_priced = picks_df["book_price"].notna().sum()
        n_no_price = picks_df["book_price"].isna().sum()
        n_bmc = (picks_df["status"] == "BOOK-MORE-CONFIDENT").sum()
        print(f"  priced: {n_priced}, no_price: {n_no_price}, BOOK-MORE-CONFIDENT: {n_bmc}")

    # D71: Write layer log
    if layer_log:
        layer_df = pd.DataFrame(layer_log)
        layer_path = out_dir / "layer_log.parquet"
        layer_df.to_parquet(layer_path, index=False)
        print(f"Layer log: {len(layer_df)} rows -> {layer_path}")

    return board_text, all_legs


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--week", type=int, default=None)
    args = parser.parse_args()

    t0 = time.time()

    week, week_games, completed = detect_week(override=args.week)
    print(f"Detected upcoming week: {week}")
    print(f"Completed games: {len(completed)}")

    week_teams = set()
    week_matchups = set()
    if len(week_games) > 0:
        week_teams = set(week_games["home_team"]) | set(week_games["away_team"])

    # If PBP doesn't have the week's games, use nflverse schedule
    if not week_teams:
        week_teams, week_matchups = get_week_teams_from_schedule(SEASON, week)

    if week_teams:
        print(f"Week {week} teams from schedule: {len(week_teams)}")

    all_lines = get_lines_from_history()
    if week_matchups:
        # Filter by exact matchups (away, home pairs)
        lines = {k: v for k, v in all_lines.items()
                 if (v["away"], v["home"]) in week_matchups}
    elif week_teams:
        lines = {k: v for k, v in all_lines.items()
                 if v["home"] in week_teams or v["away"] in week_teams}
    else:
        completed_teams = set()
        for gid in completed:
            parts = gid.split("_")
            if len(parts) >= 4:
                completed_teams.add(parts[2])
                completed_teams.add(parts[3])
        lines = {k: v for k, v in all_lines.items()
                 if v["home"] not in completed_teams or v["away"] not in completed_teams}

    print(f"Lines for week {week}: {len(lines)} games (filtered from {len(all_lines)})")
    for key, val in sorted(lines.items()):
        print(f"  {key}: spread {val['spread']:+.1f}, total {val['total']:.1f} ({val['source']})")

    # Load engine data
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    pu = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    au = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet")
    kw = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
              player_usage=pu, active_uni=au)

    # Load roster for name resolution
    roster = load_roster()
    roster_lookups = _build_roster_lookup(roster, SEASON, week)

    # Count completed games per team
    team_game_counts = count_team_completed_games(SEASON)

    # Get props pull timestamp for header
    pull_ts_str = None
    props_dir = ROOT / "data" / "odds_archive" / "nfl" / "props" / f"season={SEASON}"
    if props_dir.exists():
        for root, dirs, files in os.walk(props_dir):
            for f in files:
                if f.endswith('.parquet'):
                    pdf = pd.read_parquet(os.path.join(root, f))
                    if len(pdf) > 0 and 'pull_timestamp' in pdf.columns:
                        pull_ts_str = str(pdf['pull_timestamp'].max())
                    break
            break

    # Run anchored sims — N from params anchor block
    anchoring_log = []
    from nfl.sim.anchor import _load_anchor_params
    _ap = _load_anchor_params()
    print(f"\nSimulating {len(lines)} games at N={_ap['n_sims']} "
          f"(chunks of {_ap['chunk_size']})...")
    game_results = []
    converged_count = 0
    for key, ln in sorted(lines.items()):
        home, away = ln["home"], ln["away"]
        print(f"  Simulating {away}@{home}...", end="", flush=True)
        st = time.time()
        td, pdf, dh, da, n_iter, conv, raw_m, raw_t, anch_m, anch_t = run_anchored_chunked(
            home, away, SEASON, week, ln["spread"], ln["total"],
            anchoring_log=anchoring_log, **kw)
        dt = time.time() - st
        if conv:
            converged_count += 1
        flag = "" if conv else " [NOT CONVERGED]"
        print(f" {dt:.1f}s, {n_iter} iter, margin {anch_m:.1f} vs {ln['spread']:+.1f}{flag}")
        game_results.append({
            "home": home, "away": away, "spread": ln["spread"], "total": ln["total"],
            "source": ln["source"], "team_df": td, "player_df": pdf,
            "converged": conv, "n_iter": n_iter,
            "raw_m": raw_m, "raw_t": raw_t, "anch_m": anch_m, "anch_t": anch_t,
        })
        gc.collect()

    # Write anchoring log
    out_dir = OUT_BASE / f"week={SEASON}_{week:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    if anchoring_log:
        alog_df = pd.DataFrame(anchoring_log)
        alog_df.to_parquet(out_dir / "anchoring_log.parquet", index=False)
        # Print per-game summary: show the BEST iteration (min |err_m|+|err_t|)
        print(f"\n{'Game':16s} {'Iter':>4s} {'err_m':>6s} {'err_t':>6s} {'|m|<.5':>6s} {'|t|<1':>5s} {'2SE':>4s}")
        print("-" * 56)
        n_m05 = n_t10 = n_2se = 0
        for game, gdf in alog_df.groupby("game"):
            best_idx = (gdf['err_m'].abs() + gdf['err_t'].abs()).idxmin()
            r = gdf.loc[best_idx]
            m_ok = abs(r['err_m']) < 0.5
            t_ok = abs(r['err_t']) < 1.0
            se_ok = r['converged']
            n_m05 += m_ok; n_t10 += t_ok; n_2se += se_ok
            print(f"{game:16s} {int(r['iter'])+1:4d} {r['err_m']:+6.2f} {r['err_t']:+6.2f} "
                  f"{'Y' if m_ok else 'N':>6s} {'Y' if t_ok else 'N':>5s} "
                  f"{'Y' if se_ok else 'N':>4s}")
        n_games = alog_df["game"].nunique()
        print(f"{'TOTAL':16s}      {n_m05:6d} {n_t10:5d} {n_2se:4d} / {n_games}")

    # Build board
    board_text, all_legs = build_board(week, game_results, lines, team_game_counts,
                                        roster, roster_lookups, pull_ts_str)

    total_time = time.time() - t0
    print(f"\nTotal runtime: {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"Games simulated: {len(game_results)}")
    print(f"Converged: {converged_count}/{len(game_results)}")


if __name__ == "__main__":
    main()
