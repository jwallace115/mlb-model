#!/usr/bin/env python3
"""
ON-D11: Score forward Monday numbers against archive closes.

Input: nfl/data/own/forward/week=2026_NN.parquet files (all games kicked off).
Closes: data/odds_archive/nfl/line_history/season=SSSS/snap_*.parquet
Output: nfl/data/own/forward/scored/week=2026_NN.parquet + forward_scorecard.md

Usage:
  python3 research/own_numbers/score_forward.py --season 2026
  python3 research/own_numbers/score_forward.py --season 2026 --week 6
"""
import os, sys, argparse, glob
from datetime import datetime, timezone
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))
sys.path.insert(0, os.path.dirname(__file__))

from nfl.sim.names import FULL_TO_ABBR
from on_utils import (
    handicap_to_home_margin,
    select_close_quote,
)

ROOT = os.path.join(os.path.dirname(__file__), "../..")

# Columns that score_forward MUST NOT read from the forward file.
# The runner wrote these from the same snapshot at run time; the scorer
# re-derives closes from the full archive tape independently.
BANNED_CLOSE_COLS = [
    "hr_close_handicap", "hr_close_margin", "hr_close_price",
    "hr_close_ts", "hr_close_flag",
    "pin_close_handicap", "pin_close_margin",
    "pin_close_ts", "pin_close_flag",
]


def load_archive_tape(season):
    """Load and concatenate all line_history snaps for a season."""
    snap_dir = os.path.join(ROOT, f"data/odds_archive/nfl/line_history/season={season}")
    snap_files = sorted(glob.glob(os.path.join(snap_dir, "snap_*.parquet")))
    if not snap_files:
        print(f"HALT: no snap files in {snap_dir}")
        sys.exit(1)
    tape = pd.concat([pd.read_parquet(f) for f in snap_files], ignore_index=True)
    tape["snapshot_utc"] = pd.to_datetime(tape["snapshot_utc"], utc=True)
    tape["commence_time"] = pd.to_datetime(tape["commence_time"], utc=True)
    return tape


def american_to_implied_prob(price):
    """Convert American odds price to raw implied probability."""
    if price is None or (isinstance(price, float) and np.isnan(price)):
        return None
    if price > 0:
        return 100.0 / (price + 100.0)
    else:
        return (-price) / (-price + 100.0)


def devig_two_way(prob_a, prob_b):
    """Remove vig from a two-way market (multiplicative).
    Returns fair probability for side a."""
    if prob_a is None or prob_b is None:
        return None
    total = prob_a + prob_b
    if total <= 0:
        return None
    return prob_a / total


def score_week(fwd_df, tape, season):
    """Score a single week's forward predictions against archive closes.

    Returns a DataFrame with scored columns appended.
    """
    spreads = tape[tape["market"] == "spreads"].copy()
    spreads["team_abbr"] = spreads["outcome_name"].map(FULL_TO_ABBR)
    spreads = spreads[spreads["team_abbr"].notna()]

    rows = []
    for _, game in fwd_df.iterrows():
        event_id = game["event_id"]
        home = game["home_team"]
        away = game["away_team"]
        kick_utc = pd.to_datetime(game["kickoff_utc"])
        side = game["side"]
        confident = game["confident"]
        ours_m = game["ours_m"]

        # Decision values from the forward file (these are NOT close columns)
        hr_dec_h = game["hr_decision_handicap"]
        hr_dec_price = game.get("hr_decision_price")
        hr_dec_ts = game.get("hr_decision_ts")

        # Derive closes from archive tape (NEVER from the forward file's close cols)
        hr_close_h = hr_close_price = hr_close_ts = None
        hr_close_flag = None
        pin_close_h = pin_close_price = pin_close_ts = None
        pin_close_flag = None

        if event_id and pd.notna(event_id):
            for book, prefix in [("hardrockbet_fl", "hr"), ("pinnacle", "pin")]:
                sp = spreads[
                    (spreads["event_id"] == event_id) &
                    (spreads["bookmaker"] == book) &
                    (spreads["team_abbr"] == home)
                ]
                if len(sp) > 0:
                    cq, cflag = select_close_quote(sp, kick_utc)
                    if cq is not None:
                        if prefix == "hr":
                            hr_close_h = cq["point"]
                            hr_close_price = cq["price"]
                            hr_close_ts = str(cq["snapshot_utc"])
                            hr_close_flag = cflag
                        else:
                            pin_close_h = cq["point"]
                            pin_close_price = cq["price"]
                            pin_close_ts = str(cq["snapshot_utc"])
                            pin_close_flag = cflag

        # Convert handicaps to home margins
        hr_dec_margin = handicap_to_home_margin(hr_dec_h)
        hr_close_margin = handicap_to_home_margin(hr_close_h)
        pin_close_margin = handicap_to_home_margin(pin_close_h)

        # ── Signed movement toward our side (in points) ──
        # Movement = close_margin - decision_margin
        # "Toward our side" = positive when the line moved in our direction
        hr_movement = None
        pin_movement = None
        hr_direction = None
        pin_direction = None

        if hr_dec_margin is not None and hr_close_margin is not None:
            raw_move = hr_close_margin - hr_dec_margin
            if side == "home":
                hr_movement = raw_move   # home margin went up = our way
            elif side == "away":
                hr_movement = -raw_move  # home margin went down = our way
            if hr_movement is not None:
                if hr_movement > 0:
                    hr_direction = "moved_our_way"
                elif hr_movement < 0:
                    hr_direction = "moved_against"
                else:
                    hr_direction = "unchanged"

        if hr_dec_margin is not None and pin_close_margin is not None:
            raw_move_pin = pin_close_margin - hr_dec_margin
            if side == "home":
                pin_movement = raw_move_pin
            elif side == "away":
                pin_movement = -raw_move_pin
            if pin_movement is not None:
                if pin_movement > 0:
                    pin_direction = "moved_our_way"
                elif pin_movement < 0:
                    pin_direction = "moved_against"
                else:
                    pin_direction = "unchanged"

        # ── Paid-price CLV (LM-1b scale rule) ──
        # = Pinnacle de-vigged close prob (our side) − HR RAW decision implied prob (our side)
        # Only when same-point (decision handicap == close handicap)
        clv = None
        clv_flag = None
        same_point = (hr_dec_h is not None and pin_close_h is not None and
                      not (isinstance(hr_dec_h, float) and np.isnan(hr_dec_h)) and
                      not (isinstance(pin_close_h, float) and np.isnan(pin_close_h)) and
                      abs(hr_dec_h - pin_close_h) < 0.001)

        if same_point:
            # Need Pinnacle close prices for both sides to devig
            if event_id and pd.notna(event_id):
                pin_sp_home = spreads[
                    (spreads["event_id"] == event_id) &
                    (spreads["bookmaker"] == "pinnacle") &
                    (spreads["team_abbr"] == home)
                ]
                pin_sp_away = spreads[
                    (spreads["event_id"] == event_id) &
                    (spreads["bookmaker"] == "pinnacle") &
                    (spreads["team_abbr"] == away)
                ]
                pin_home_cq, _ = select_close_quote(pin_sp_home, kick_utc)
                pin_away_cq, _ = select_close_quote(pin_sp_away, kick_utc)

                if pin_home_cq is not None and pin_away_cq is not None:
                    pin_home_imp = american_to_implied_prob(pin_home_cq["price"])
                    pin_away_imp = american_to_implied_prob(pin_away_cq["price"])
                    pin_fair_home = devig_two_way(pin_home_imp, pin_away_imp)
                    pin_fair_away = devig_two_way(pin_away_imp, pin_home_imp)

                    hr_dec_imp_raw = american_to_implied_prob(hr_dec_price)

                    if pin_fair_home is not None and hr_dec_imp_raw is not None:
                        if side == "home":
                            clv = pin_fair_home - hr_dec_imp_raw
                        elif side == "away":
                            clv = pin_fair_away - (1.0 - hr_dec_imp_raw)
                        clv_flag = "same_point"
        else:
            clv_flag = "incomparable"

        # ── ATS results (placeholder — needs pbp_2026) ──
        # Will be filled when results are available
        ats_decision = None
        ats_close = None

        row = {
            # Forward file columns (pass through)
            "game_id": game["game_id"],
            "season": game["season"],
            "week": game["week"],
            "home_team": home,
            "away_team": away,
            "kickoff_utc": game["kickoff_utc"],
            "prediction_cutoff_utc": game["prediction_cutoff_utc"],
            "ours_m": ours_m,
            "ours_t": game["ours_t"],
            "err_m": game["err_m"],
            "err_t": game["err_t"],
            "mode": game["mode"],
            # Decision (from forward file)
            "hr_decision_handicap": hr_dec_h,
            "hr_decision_margin": hr_dec_margin,
            "hr_decision_price": hr_dec_price,
            "hr_decision_ts": hr_dec_ts,
            "gap_vs_hr": game["gap_vs_hr"],
            "confident": confident,
            "side": side,
            "event_id": event_id,
            # Close (derived from archive tape)
            "scored_hr_close_handicap": hr_close_h,
            "scored_hr_close_margin": hr_close_margin,
            "scored_hr_close_price": hr_close_price,
            "scored_hr_close_ts": hr_close_ts,
            "scored_hr_close_flag": hr_close_flag,
            "scored_pin_close_handicap": pin_close_h,
            "scored_pin_close_margin": pin_close_margin,
            "scored_pin_close_price": pin_close_price,
            "scored_pin_close_ts": pin_close_ts,
            "scored_pin_close_flag": pin_close_flag,
            # Scoring
            "hr_movement": hr_movement,
            "hr_direction": hr_direction,
            "pin_movement": pin_movement,
            "pin_direction": pin_direction,
            "clv": clv,
            "clv_flag": clv_flag,
            "ats_decision": ats_decision,
            "ats_close": ats_close,
        }
        rows.append(row)

    return pd.DataFrame(rows)


def week_bucket(week):
    """Assign week to bucket: 1-6, 7-12, 13+."""
    if week <= 6:
        return "1-6"
    elif week <= 12:
        return "7-12"
    else:
        return "13+"


def format_scorecard(scored_dfs, season):
    """Build forward_scorecard.md content from scored DataFrames."""
    lines = []
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines.append(f"\n## Forward Scorecard — Season {season} (scored {run_ts})\n")

    all_scored = pd.concat(scored_dfs, ignore_index=True)
    all_scored["week_bucket"] = all_scored["week"].apply(week_bucket)

    for mode_label in ["PRIMARY", "PILOT"]:
        mode_df = all_scored[all_scored["mode"] == mode_label]
        if mode_df.empty:
            continue

        lines.append(f"### {mode_label} weeks\n")

        # Per-week table
        lines.append("#### Per-week summary (confident games only)\n")
        lines.append("| Week | Mode | N | Moved | Dir% | Mean HR Move | Mean Pin Move |")
        lines.append("|------|------|---|-------|------|--------------|---------------|")

        for wk in sorted(mode_df["week"].unique()):
            wk_df = mode_df[(mode_df["week"] == wk) & (mode_df["confident"])]
            n = len(wk_df)
            moved = wk_df["hr_direction"].isin(["moved_our_way", "moved_against"]).sum()
            dir_our = (wk_df["hr_direction"] == "moved_our_way").sum()
            dir_pct = f"{dir_our/moved:.1%}" if moved > 0 else "N/A"
            mean_hr = f"{wk_df['hr_movement'].mean():+.3f}" if n > 0 and wk_df["hr_movement"].notna().any() else "N/A"
            mean_pin = f"{wk_df['pin_movement'].mean():+.3f}" if n > 0 and wk_df["pin_movement"].notna().any() else "N/A"
            lines.append(f"| {wk} | {mode_label} | {n} | {moved} | {dir_pct} | {mean_hr} | {mean_pin} |")

        lines.append("")

        # Cumulative
        conf = mode_df[mode_df["confident"]]
        lines.append("#### Cumulative (confident)\n")
        n = len(conf)
        moved = conf["hr_direction"].isin(["moved_our_way", "moved_against"]).sum()
        dir_our = (conf["hr_direction"] == "moved_our_way").sum()
        dir_pct = f"{dir_our/moved:.1%}" if moved > 0 else "N/A"
        mean_hr = f"{conf['hr_movement'].mean():+.3f}" if n > 0 and conf["hr_movement"].notna().any() else "N/A"
        mean_pin = f"{conf['pin_movement'].mean():+.3f}" if n > 0 and conf["pin_movement"].notna().any() else "N/A"
        lines.append(f"- Games: {n}, Moved: {moved}, Direction: {dir_pct} ({dir_our}/{moved if moved > 0 else 0})")
        lines.append(f"- Mean HR movement: {mean_hr}")
        lines.append(f"- Mean Pinnacle movement: {mean_pin}")

        # By dog/favorite
        if n > 0:
            lines.append("\n#### By dog/favorite pick (confident)\n")
            lines.append("| Pick | N | Moved | Dir% | Mean HR Move |")
            lines.append("|------|---|-------|------|--------------|")
            # Determine if pick is dog or favorite based on hr_decision_handicap
            for pick_label, mask_fn in [
                ("Dog", lambda df: df.apply(
                    lambda r: (r["side"] == "home" and r.get("hr_decision_handicap", 0) and r["hr_decision_handicap"] > 0)
                              or (r["side"] == "away" and r.get("hr_decision_handicap", 0) and r["hr_decision_handicap"] < 0),
                    axis=1)),
                ("Fav", lambda df: df.apply(
                    lambda r: (r["side"] == "home" and r.get("hr_decision_handicap", 0) and r["hr_decision_handicap"] < 0)
                              or (r["side"] == "away" and r.get("hr_decision_handicap", 0) and r["hr_decision_handicap"] > 0),
                    axis=1)),
            ]:
                try:
                    sub = conf[mask_fn(conf)]
                except Exception:
                    sub = pd.DataFrame()
                sn = len(sub)
                sm = sub["hr_direction"].isin(["moved_our_way", "moved_against"]).sum()
                sd = (sub["hr_direction"] == "moved_our_way").sum()
                sdp = f"{sd/sm:.1%}" if sm > 0 else "N/A"
                smh = f"{sub['hr_movement'].mean():+.3f}" if sn > 0 and sub["hr_movement"].notna().any() else "N/A"
                lines.append(f"| {pick_label} | {sn} | {sm} | {sdp} | {smh} |")

        # By week bucket
        lines.append("\n#### By week bucket (confident)\n")
        lines.append("| Bucket | N | Moved | Dir% | Mean HR Move |")
        lines.append("|--------|---|-------|------|--------------|")
        for bucket in ["1-6", "7-12", "13+"]:
            sub = conf[conf["week_bucket"] == bucket]
            sn = len(sub)
            if sn == 0:
                continue
            sm = sub["hr_direction"].isin(["moved_our_way", "moved_against"]).sum()
            sd = (sub["hr_direction"] == "moved_our_way").sum()
            sdp = f"{sd/sm:.1%}" if sm > 0 else "N/A"
            smh = f"{sub['hr_movement'].mean():+.3f}" if sn > 0 and sub["hr_movement"].notna().any() else "N/A"
            lines.append(f"| {bucket} | {sn} | {sm} | {sdp} | {smh} |")

        # CLV summary
        clv_valid = conf[conf["clv_flag"] == "same_point"]
        if len(clv_valid) > 0:
            lines.append(f"\n#### CLV (same-point, confident)")
            lines.append(f"\n- N: {len(clv_valid)}")
            lines.append(f"- Mean CLV: {clv_valid['clv'].mean():+.4f}")
            lines.append(f"- Median CLV: {clv_valid['clv'].median():+.4f}")

        lines.append("")

    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Score forward Monday numbers")
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, default=None,
                        help="Score a specific week (default: all eligible)")
    args = parser.parse_args()
    season = args.season

    # Find forward week files
    fwd_dir = os.path.join(ROOT, "nfl/data/own/forward")
    if args.week:
        fwd_files = [os.path.join(fwd_dir, f"week={season}_{args.week:02d}.parquet")]
        fwd_files = [f for f in fwd_files if os.path.exists(f)]
    else:
        fwd_files = sorted(glob.glob(os.path.join(fwd_dir, f"week={season}_*.parquet")))
        # Exclude DRYRUN files
        fwd_files = [f for f in fwd_files if "DRYRUN" not in f]

    if not fwd_files:
        print(f"No forward files found for season {season}")
        sys.exit(0)

    # Load archive tape once
    print(f"Loading archive tape for season {season}...")
    tape = load_archive_tape(season)
    spreads_tape = tape[tape["market"] == "spreads"]
    print(f"Archive tape: {len(tape)} rows, {len(spreads_tape)} spreads")

    now_utc = datetime.now(timezone.utc)
    scored_dfs = []
    skipped = []

    for fwd_path in fwd_files:
        fname = os.path.basename(fwd_path)
        # Extract week from filename
        # Format: week=SSSS_WW.parquet
        wk_str = fname.replace(".parquet", "").split("=")[1].split("_")[1]
        wk = int(wk_str)

        fwd_df = pd.read_parquet(fwd_path)

        # Check if ALL games have kicked off
        all_kicked = True
        unplayed = []
        for _, g in fwd_df.iterrows():
            kick = pd.to_datetime(g["kickoff_utc"])
            if kick.tzinfo is None:
                kick = kick.tz_localize("UTC")
            if kick >= now_utc:
                all_kicked = False
                unplayed.append(g["game_id"])

        if not all_kicked:
            skipped.append((wk, unplayed))
            print(f"SKIP week {wk}: {len(unplayed)} unplayed games: {unplayed[:5]}")
            continue

        # Check scored output doesn't already exist
        scored_dir = os.path.join(ROOT, "nfl/data/own/forward/scored")
        scored_path = os.path.join(scored_dir, f"week={season}_{wk:02d}.parquet")
        if os.path.exists(scored_path):
            print(f"HALT: {scored_path} already exists (revision 0 only)")
            sys.exit(1)

        print(f"\nScoring week {wk} ({len(fwd_df)} games)...")
        scored = score_week(fwd_df, tape, season)
        scored_dfs.append(scored)

        # Write scored parquet
        os.makedirs(scored_dir, exist_ok=True)
        scored.to_parquet(scored_path, index=False)
        print(f"  Saved: {scored_path}")

        # Report summary
        conf = scored[scored["confident"]]
        n_conf = len(conf)
        moved = conf["hr_direction"].isin(["moved_our_way", "moved_against"]).sum()
        dir_our = (conf["hr_direction"] == "moved_our_way").sum()
        print(f"  Confident: {n_conf}, Moved: {moved}, Direction: "
              f"{dir_our}/{moved} ({dir_our/moved:.1%})" if moved > 0 else f"  Confident: {n_conf}")

    # Write scorecard
    if scored_dfs:
        scorecard_path = os.path.join(ROOT, "research/own_numbers/forward_scorecard.md")
        content = format_scorecard(scored_dfs, season)

        if not os.path.exists(scorecard_path):
            with open(scorecard_path, "w") as f:
                f.write("# ON Forward Scorecard\n\nScoring record for forward Monday numbers.\n")

        with open(scorecard_path, "a") as f:
            f.write(content)
        print(f"\nScorecard appended: {scorecard_path}")

    # Report skipped weeks
    if skipped:
        print(f"\nSkipped weeks (unplayed games):")
        for wk, games in skipped:
            print(f"  Week {wk}: {len(games)} unplayed — {games[:5]}")

    if not scored_dfs:
        print("\nNo weeks were eligible for scoring.")


if __name__ == "__main__":
    main()
