#!/usr/bin/env python3
"""
Phase 4A: Weekly NFL sim runner. Idempotent, re-runnable as lines move.

Usage: python3 nfl/sim/run_week.py

DETECTS the upcoming week from the nflverse schedule (first regular-season week
with unplayed games). Never takes a typed week number.
"""

import sys, os, time, json, gc, subprocess
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.sim.engine import simulate_game, _load_tables, _load_ratings

SEASON = 2026
OUT_BASE = ROOT / "nfl" / "data" / "sim" / "outputs"
J_INV = np.array([[0.07450484, 0.10168527], [-0.08895527, 0.1277827]])

# Full name -> abbreviation
TEAM_MAP = {
    'Arizona Cardinals':'ARI','Atlanta Falcons':'ATL','Baltimore Ravens':'BAL',
    'Buffalo Bills':'BUF','Carolina Panthers':'CAR','Chicago Bears':'CHI',
    'Cincinnati Bengals':'CIN','Cleveland Browns':'CLE','Dallas Cowboys':'DAL',
    'Denver Broncos':'DEN','Detroit Lions':'DET','Green Bay Packers':'GB',
    'Houston Texans':'HOU','Indianapolis Colts':'IND','Jacksonville Jaguars':'JAX',
    'Kansas City Chiefs':'KC','Las Vegas Raiders':'LV','Los Angeles Chargers':'LAC',
    'Los Angeles Rams':'LA','Miami Dolphins':'MIA','Minnesota Vikings':'MIN',
    'New England Patriots':'NE','New Orleans Saints':'NO','New York Giants':'NYG',
    'New York Jets':'NYJ','Philadelphia Eagles':'PHI','Pittsburgh Steelers':'PIT',
    'San Francisco 49ers':'SF','Seattle Seahawks':'SEA','Tampa Bay Buccaneers':'TB',
    'Tennessee Titans':'TEN','Washington Commanders':'WAS',
}
TEAM_MAP_INV = {v: k for k, v in TEAM_MAP.items()}


def detect_week():
    """Detect the upcoming week from PBP data."""
    pbp_path = ROOT / "nfl" / "data" / "pbp" / f"pbp_{SEASON}.parquet"
    if not pbp_path.exists():
        raise FileNotFoundError(f"No PBP for {SEASON}. Run pull_pbp.py first.")
    df = pd.read_parquet(pbp_path, columns=["game_id", "season", "week",
                                             "home_team", "away_team",
                                             "home_score", "away_score"])
    games = df.drop_duplicates("game_id")
    # Completed = has non-null, non-zero scores
    completed = set(games[games["home_score"].notna() & (games["home_score"] > 0)]["game_id"])
    # Find first week with incomplete games
    for w in sorted(games["week"].unique()):
        wk = games[games["week"] == w]
        if not wk["game_id"].isin(completed).all():
            # This week still has unplayed games
            unplayed = wk[~wk["game_id"].isin(completed)]
            return w, unplayed, completed
    # All weeks complete — next week is max + 1
    return int(games["week"].max()) + 1, pd.DataFrame(), completed


def get_lines_from_history():
    """Get latest Hard Rock spread/total from line_history."""
    lh_dir = ROOT / "data" / "odds_archive" / "nfl" / "line_history" / f"season={SEASON}"
    if not lh_dir.exists():
        return {}
    files = sorted(lh_dir.glob("*.parquet"))
    if not files:
        return {}
    df = pd.read_parquet(files[-1])
    # Prefer hardrockbet_fl, fallback to consensus median
    lines = {}
    for (home_full, away_full), gdf in df.groupby(["home_team", "away_team"]):
        home = TEAM_MAP.get(home_full, home_full)
        away = TEAM_MAP.get(away_full, away_full)
        hr = gdf[gdf["bookmaker"].str.contains("hardrock", case=False, na=False)]
        if hr.empty:
            hr = gdf  # fallback to all books
        # Spread
        spreads = hr[hr["market"] == "spreads"]
        home_sp = spreads[spreads["outcome_name"].apply(lambda x: home_full.split()[-1] in str(x) if x else False)]
        if not home_sp.empty:
            spread = float(home_sp["point"].iloc[0])
        else:
            spread = None
        # Total
        totals = hr[hr["market"] == "totals"]
        over = totals[totals["outcome_name"] == "Over"]
        if not over.empty:
            total = float(over["point"].iloc[0])
        else:
            total = None
        if spread is not None and total is not None:
            source = "hardrockbet_fl" if "hardrock" in str(hr["bookmaker"].iloc[0]).lower() else "consensus"
            lines[f"{away}@{home}"] = {
                "home": home, "away": away, "spread": spread, "total": total,
                "source": source,
            }
    return lines


def run_anchored_game(home, away, season, week, spread, total, n_sims, **kw):
    """Run up to 5 anchoring iterations with SE-aware stopping."""
    dh, da = 0.0, 0.0
    raw_m = raw_t = None
    for it in range(5):
        result = simulate_game(
            home, away, season, week, n_sims=n_sims, seed=hash((home, away, season, week, 42)) % (2**31),
            epa_home_offset=dh, epa_away_offset=da, **kw)
        if isinstance(result, tuple):
            td, pdf = result
        else:
            td, pdf = result, None
        margin = (td["home_score"] - td["away_score"]).values.astype(float)
        total_arr = (td["home_score"] + td["away_score"]).values.astype(float)
        m = margin.mean(); t = total_arr.mean()
        se_m = margin.std() / np.sqrt(n_sims)
        se_t = total_arr.std() / np.sqrt(n_sims)
        if it == 0:
            raw_m, raw_t = m, t
        me = spread - m; te = total - t
        thr_m = max(0.25, 2 * se_m)
        thr_t = max(0.5, 2 * se_t)
        if abs(me) < thr_m and abs(te) < thr_t:
            return td, pdf, dh, da, it + 1, True, raw_m, raw_t, m, t
        step = J_INV @ np.array([me, te])
        dh += step[0]; da += step[1]
        if it < 4: del td, pdf
    return td, pdf, dh, da, 5, False, raw_m, raw_t, m, t


def build_board(week, game_results, lines_used):
    """Write parlay_board.md."""
    out_dir = OUT_BASE / f"week={SEASON}_{week:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Load calibration
    cal_path = ROOT / "nfl" / "sim" / "calibration_v1.json"
    cal_maps = {}
    if cal_path.exists():
        with open(cal_path) as f:
            cal_maps = json.load(f).get("maps", {})

    board_lines = []
    board_lines.append(f"# NFL Week {week} ({SEASON}) Parlay Board")
    board_lines.append(f"\nGenerated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    board_lines.append("")

    all_trusted_legs = []

    for gr in game_results:
        home = gr["home"]; away = gr["away"]
        td = gr["team_df"]; pdf = gr.get("player_df")
        spread = gr["spread"]; total_line = gr["total"]
        converged = gr["converged"]

        margin = (td["home_score"] - td["away_score"]).values.astype(float)
        total_arr = (td["home_score"] + td["away_score"]).values.astype(float)

        flag = " [NOT ANCHORED]" if not converged else ""
        board_lines.append(f"## {away} @ {home}{flag}")
        board_lines.append(f"Hard Rock: spread {spread:+.1f} / total {total_line:.1f} ({gr['source']})")
        board_lines.append(f"Anchored: margin {margin.mean():.1f} / total {total_arr.mean():.1f}")
        board_lines.append("")

        # Player props (trusted: WR/TE receptions, WR anytime TD)
        if pdf is not None and len(pdf) > 0:
            pmeans = pdf.groupby(["player_id", "player_name", "position", "team"]).agg(
                mean_tgt=("targets", "mean"),
                mean_car=("carries", "mean"),
            ).reset_index()

            N = len(td)
            board_lines.append("### Trusted props (WR/TE receptions, WR anytime TD)")
            board_lines.append("")
            board_lines.append("| Player | Pos | Prop | Line | Sim P | Cal P |")
            board_lines.append("|--------|-----|------|------|-------|-------|")

            for team in [home, away]:
                tp = pmeans[pmeans["team"] == team]
                top = tp.nlargest(6, "mean_tgt")
                for _, p in top.iterrows():
                    if p["position"] not in ("WR", "TE"):
                        continue
                    pid = p["player_id"]
                    pname = p["player_name"]
                    pos = p["position"]
                    psims = pdf[pdf["player_id"] == pid]
                    stats = pd.DataFrame({"sim_id": np.arange(N)}).merge(
                        psims[["sim_id", "receptions", "anytime_td"]],
                        on="sim_id", how="left").fillna(0)

                    # Reception props
                    for k in [2, 3, 4, 5, 6, 7]:
                        sim_p = float((stats["receptions"] >= k).mean())
                        if sim_p < 0.05 or sim_p > 0.95:
                            continue
                        cal_key = f"prop_rec_{pos}"
                        if cal_key in cal_maps:
                            cal_p = float(np.interp(sim_p,
                                np.array(cal_maps[cal_key]["x"]),
                                np.array(cal_maps[cal_key]["y"])))
                        else:
                            cal_p = sim_p
                        flag_te = " [TE]" if pos == "TE" else ""
                        board_lines.append(
                            f"| {pname[:18]:18s} | {pos} | rec >= {k} | {k-0.5:.1f} | {sim_p:.3f} | {cal_p:.3f} |")
                        all_trusted_legs.append({
                            "game": f"{away}@{home}", "player": pname, "pos": pos,
                            "prop": f"rec >= {k}", "line": k - 0.5,
                            "sim_p": sim_p, "cal_p": cal_p, "family": "receptions",
                        })

                    # Anytime TD (WR only)
                    if pos == "WR":
                        atd_p = float((stats["anytime_td"] >= 1).mean())
                        if 0.05 < atd_p < 0.95:
                            cal_key = f"prop_atd_{pos}"
                            if cal_key in cal_maps:
                                cal_atd = float(np.interp(atd_p,
                                    np.array(cal_maps[cal_key]["x"]),
                                    np.array(cal_maps[cal_key]["y"])))
                            else:
                                cal_atd = atd_p
                            board_lines.append(
                                f"| {pname[:18]:18s} | {pos} | anytime TD | 0.5 | {atd_p:.3f} | {cal_atd:.3f} |")
                            all_trusted_legs.append({
                                "game": f"{away}@{home}", "player": pname, "pos": pos,
                                "prop": "anytime TD", "line": 0.5,
                                "sim_p": atd_p, "cal_p": cal_atd, "family": "atd",
                            })

            board_lines.append("")

        # Game markets (alt spread/total with key-number flag)
        board_lines.append("### Game markets")
        board_lines.append("")
        p_hw = (margin > 0).mean()
        p_hc = (margin - spread > 0).mean()
        p_ov = (total_arr > total_line).mean()
        board_lines.append(f"P(home win) = {p_hw:.3f} | P(home cover) = {p_hc:.3f} | P(over) = {p_ov:.3f}")
        board_lines.append("")

        # Key number flags
        p_m3 = (np.abs(margin) == 3).mean()
        if p_m3 < 0.10:
            board_lines.append(f"**KEY-NUMBER FLAG**: P(|margin|=3) = {p_m3*100:.1f}% (actual ~14.5%). "
                             f"Alt spreads at +/-3 and +/-6 UNRELIABLE.")
        board_lines.append("")
        board_lines.append("---")
        board_lines.append("")

    # Cross-game volume legs
    if all_trusted_legs:
        board_lines.append("## Cross-game volume legs (top 20 trusted by calibrated P)")
        board_lines.append("")
        board_lines.append("| Game | Player | Prop | Cal P |")
        board_lines.append("|------|--------|------|-------|")
        sorted_legs = sorted(all_trusted_legs, key=lambda x: -x["cal_p"])
        for leg in sorted_legs[:20]:
            board_lines.append(
                f"| {leg['game']:15s} | {leg['player'][:15]:15s} | {leg['prop']:12s} | {leg['cal_p']:.3f} |")

    board_text = "\n".join(board_lines)

    with open(out_dir / "parlay_board.md", "w") as f:
        f.write(board_text)
    print(f"Board written to {out_dir / 'parlay_board.md'}")
    return board_text


def main():
    t0 = time.time()

    # Stage 1: Detect week
    week, unplayed, completed = detect_week()
    print(f"Detected upcoming week: {week}")
    print(f"Completed games: {len(completed)}")

    # Stage 2: Get lines
    lines = get_lines_from_history()
    print(f"Lines available: {len(lines)} games")
    for key, val in sorted(lines.items()):
        print(f"  {key}: spread {val['spread']:+.1f}, total {val['total']:.1f} ({val['source']})")

    # Stage 3: Load engine data
    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    pu = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    au = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet")
    kw = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
              player_usage=pu, active_uni=au)

    # Stage 4: Run anchored sims
    N_SIMS = 2000  # 10000 is ideal but 2000 for speed in this first run
    game_results = []
    for key, ln in sorted(lines.items()):
        home, away = ln["home"], ln["away"]
        print(f"  Simulating {away}@{home}...", end="", flush=True)
        st = time.time()
        td, pdf, dh, da, n_iter, conv, raw_m, raw_t, anch_m, anch_t = run_anchored_game(
            home, away, SEASON, week, ln["spread"], ln["total"], N_SIMS, **kw)
        dt = time.time() - st
        flag = "" if conv else " [NOT CONVERGED]"
        print(f" {dt:.1f}s, {n_iter} iter, margin {anch_m:.1f} vs {ln['spread']:+.1f}{flag}")
        game_results.append({
            "home": home, "away": away, "spread": ln["spread"], "total": ln["total"],
            "source": ln["source"], "team_df": td, "player_df": pdf,
            "converged": conv, "n_iter": n_iter,
            "raw_m": raw_m, "raw_t": raw_t, "anch_m": anch_m, "anch_t": anch_t,
        })
        del td, pdf
        gc.collect()

    # Stage 5: Build board
    board = build_board(week, game_results, lines)

    total_time = time.time() - t0
    print(f"\nTotal runtime: {total_time:.0f}s ({total_time/60:.1f} min)")
    print(f"Games simulated: {len(game_results)}")


if __name__ == "__main__":
    main()
