#!/usr/bin/env python3
"""
NRFI Parlay Helper — Daily Runner & Grader
============================================
Shadow-tracks a frozen micro model for NRFI parlay leg quality.
NOT a betting signal. Research filter only.

Usage:
  python3 mlb/pipeline/nrfi_helper_daily.py                  # score today
  python3 mlb/pipeline/nrfi_helper_daily.py --date 2026-04-07
  python3 mlb/pipeline/nrfi_helper_daily.py --grade           # grade unresolved
"""

import argparse
import json
import os
import pickle
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
os.chdir(PROJECT_ROOT)

SHADOW_LOG = PROJECT_ROOT / "research" / "mlb_first_inning" / "nrfi_shadow_log_2026.json"
MODEL_DIR = PROJECT_ROOT / "research" / "mlb_first_inning"
MLB_API = "https://statsapi.mlb.com/api/v1"

# Schedule uses 3-letter codes; hitter/pitcher game logs use different abbreviations
_SCHED_TO_HGL = {
    "TBR": "TB", "SDP": "SD", "WSN": "WSH", "CHW": "CWS",
    "KCR": "KC", "SFG": "SF", "ARI": "AZ", "OAK": "ATH",
}

def _norm_team(abbr: str) -> str:
    """Normalize schedule team abbreviation to hitter/pitcher game log abbreviation."""
    return _SCHED_TO_HGL.get(abbr, abbr)


# ── Model loading ────────────────────────────────────────────────────────────

def _load_models():
    with open(MODEL_DIR / "micro_model_top1.pkl", "rb") as f:
        top1 = pickle.load(f)
    with open(MODEL_DIR / "micro_model_bot1.pkl", "rb") as f:
        bot1 = pickle.load(f)
    arch = None
    arch_path = MODEL_DIR / "starter_archetype_model.pkl"
    if arch_path.exists():
        with open(arch_path, "rb") as f:
            arch = pickle.load(f)
    return top1, bot1, arch


def _classify_starter_archetype(sp_id, pgl, sc_ps, arch_artifact):
    """Classify a starter's archetype from rolling stats. Returns label string or None."""
    if arch_artifact is None or sp_id is None:
        return None
    km = arch_artifact["kmeans"]
    scaler = arch_artifact["scaler"]
    label_map = arch_artifact["label_map"]

    # Compute rolling 5-start features for this pitcher
    sp = pgl[pgl["player_id"] == sp_id].sort_values("game_date")
    if len(sp) < 2:
        return None
    sp = sp.copy()
    sp["bb_rate_p"] = sp["walks"] / sp["batters_faced"].clip(lower=1)
    bb_r5 = sp["bb_rate_p"].rolling(5, min_periods=2).mean().iloc[-1]

    # Statcast rolling
    sc = sc_ps[sc_ps["pitcher_id"] == sp_id].sort_values("game_date") if sc_ps is not None else pd.DataFrame()
    if len(sc) < 2:
        return None
    whiff_r5 = sc["whiff_rate"].rolling(5, min_periods=2).mean().iloc[-1]
    hh_r5 = sc["hard_hit_rate"].rolling(5, min_periods=2).mean().iloc[-1]

    if any(pd.isna([whiff_r5, bb_r5, hh_r5])):
        return None

    vec = np.array([[whiff_r5, bb_r5, hh_r5]])
    cluster = int(km.predict(scaler.transform(vec))[0])
    return label_map.get(cluster)


# ── Feature building ─────────────────────────────────────────────────────────

def _build_features_for_game(game: dict, hgl: pd.DataFrame, pgl: pd.DataFrame,
                              tto: pd.DataFrame, gt: pd.DataFrame) -> dict | None:
    """Build micro model features for a single game using historical data."""
    game_pk = game["game_pk"]
    home = game["home_team"]
    away = game["away_team"]
    home_hgl = _norm_team(home)
    away_hgl = _norm_team(away)
    home_sp_id = game.get("home_probable_pitcher", {}).get("id")
    away_sp_id = game.get("away_probable_pitcher", {}).get("id")
    home_sp_hand = game.get("home_probable_pitcher", {}).get("throws", "")
    away_sp_hand = game.get("away_probable_pitcher", {}).get("throws", "")

    feats = {"game_pk": game_pk, "home_team": home, "away_team": away}

    # ── Top-3 offense rolling 15 (team-level, from historical game logs) ──
    for side, team, opp_sp_hand in [("away", away_hgl, home_sp_hand), ("home", home_hgl, away_sp_hand)]:
        team_games = hgl[(hgl["team"] == team) & (hgl["batting_order_position"].isin([1, 2, 3]))].copy()
        if len(team_games) == 0:
            return None

        per_game = team_games.groupby("game_pk").agg(
            obp=("obp", "mean"), slg=("slg", "mean"),
            iso=("iso", "mean"),
            k=("strikeouts", "sum"), pa=("plate_appearances", "sum"),
        )
        per_game["k_rate"] = per_game["k"] / per_game["pa"].clip(lower=1)
        per_game = per_game.merge(
            hgl[["game_pk", "game_date"]].drop_duplicates(), on="game_pk"
        ).sort_values("game_date")

        for col in ["obp", "slg", "iso", "k_rate"]:
            r = per_game[col].shift(1).rolling(15, min_periods=5).mean()
            feats[f"{side}_t3_{col}_r15"] = r.iloc[-1] if len(r) > 0 and pd.notna(r.iloc[-1]) else None

        # Platoon (today's matchup)
        today_top3 = team_games.sort_values("game_date").groupby("game_pk").tail(3)
        if len(today_top3) >= 3:
            last_game = today_top3[today_top3["game_pk"] == today_top3["game_pk"].iloc[-1]]
            if len(last_game) == 3 and opp_sp_hand in ("L", "R"):
                plat = np.mean([
                    1 if h == "S" else (1 if h != opp_sp_hand else 0)
                    for h in last_game["batter_hand"].values
                ])
                feats[f"{side}_plat_frac"] = plat
            else:
                feats[f"{side}_plat_frac"] = 0.58  # population mean fallback
        else:
            feats[f"{side}_plat_frac"] = 0.58

    # ── Pitcher rolling 5 ──
    for prefix, sp_id in [("hsp", home_sp_id), ("asp", away_sp_id)]:
        if sp_id is None:
            feats[f"{prefix}_era_r5"] = None
            feats[f"{prefix}_bb9_r5"] = None
            continue
        sp_games = pgl[pgl["player_id"] == sp_id].sort_values("game_date")
        if len(sp_games) < 2:
            feats[f"{prefix}_era_r5"] = None
            feats[f"{prefix}_bb9_r5"] = None
            continue
        sp_games = sp_games.copy()
        sp_games["era_ps"] = sp_games["earned_runs"] / sp_games["innings_pitched"].clip(lower=0.1) * 9
        sp_games["bb9"] = sp_games["walks"] / sp_games["innings_pitched"].clip(lower=0.1) * 9
        for col in ["era_ps", "bb9"]:
            r = sp_games[col].rolling(5, min_periods=2).mean()
            feats[f"{prefix}_{col.replace('era_ps','era')}_r5" if col == "era_ps" else f"{prefix}_{col}_r5"] = (
                r.iloc[-1] if len(r) > 0 and pd.notna(r.iloc[-1]) else None
            )

    # ── TTO1 ──
    for prefix, sp_id, side in [("home", home_sp_id, "home"), ("away", away_sp_id, "away")]:  # TTO uses pitcher_id, not team
        if sp_id is None:
            feats[f"{side}_sp_tto1"] = None
            continue
        sp_tto = tto[tto["pitcher_id"] == sp_id].sort_values("game_date")
        if len(sp_tto) > 0 and pd.notna(sp_tto["pitcher_woba_tto1_rolling"].iloc[-1]):
            feats[f"{side}_sp_tto1"] = sp_tto["pitcher_woba_tto1_rolling"].iloc[-1]
        else:
            feats[f"{side}_sp_tto1"] = None

    # ── Environment ──
    # Use game_table if available, otherwise fetch weather
    gt_row = gt[gt["game_pk"] == game_pk]
    if len(gt_row) > 0:
        row = gt_row.iloc[0]
        feats["park_factor_hr"] = row.get("park_factor_hr")
        feats["temperature"] = row.get("temperature")
        feats["wind_speed"] = row.get("wind_speed")
        feats["dome"] = 1 if row.get("roof_status") in ("closed", "dome") else 0
    else:
        # Defaults for current-day games not yet in game_table
        try:
            from config import STADIUMS
            venue = game.get("venue_name", "")
            stadium = STADIUMS.get(game["home_team"], {})
            feats["park_factor_hr"] = stadium.get("park_factor", 100)
            feats["dome"] = 1 if stadium.get("roof") in ("dome", "retractable") else 0
        except Exception:
            feats["park_factor_hr"] = 100
            feats["dome"] = 0
        feats["temperature"] = 72.0  # fallback — weather not critical for ranking
        feats["wind_speed"] = 5.0

    return feats


# ── Scoring ──────────────────────────────────────────────────────────────────

def run_daily(game_date: str | None = None):
    game_date = game_date or date.today().isoformat()

    # Load existing log
    log = json.load(open(SHADOW_LOG)) if SHADOW_LOG.exists() else []
    existing_dates = set(e["date"] for e in log)
    if game_date in existing_dates:
        print(f"Date {game_date} already logged ({sum(1 for e in log if e['date'] == game_date)} games). Skipping.")
        return

    # Fetch schedule
    from modules.schedule import fetch_schedule
    games = fetch_schedule(game_date)
    if not games:
        print(f"No games for {game_date}.")
        return

    # Load models + historical data
    top1_art, bot1_art, arch_art = _load_models()
    hgl = pd.read_parquet("mlb/data/hitter_game_logs.parquet")
    hgl = hgl[hgl["starter_flag"] == 1].copy()
    pgl = pd.read_parquet("mlb/data/pitcher_game_logs.parquet")
    pgl = pgl[pgl["starter_flag"] == 1].copy()
    tto = pd.read_parquet("research/data_pulls/pitcher_tto_splits.parquet")
    gt = pd.read_parquet("sim/data/game_table.parquet")

    # Load Statcast per-start for archetype classification
    sc_ps = None
    try:
        sc_ps = pd.read_parquet("research/statcast_enrichment/pitcher_statcast_per_start.parquet")
        sc_ps = sc_ps.sort_values(["pitcher_id", "game_date"])
    except Exception:
        pass

    # Build features for each game
    rows = []
    dropped = []
    for g in games:
        feats = _build_features_for_game(g, hgl, pgl, tto, gt)
        if feats is None:
            dropped.append({"game_pk": g["game_pk"], "home_team": g["home_team"],
                            "away_team": g["away_team"], "drop_reason": "no_lineup_history"})
            continue
        feats["_game"] = g
        rows.append(feats)

    # Score
    def _has_missing(vals):
        return any(v is None or (isinstance(v, float) and np.isnan(v)) for v in vals)

    scored = []
    if rows:
        feat_df = pd.DataFrame(rows)
        for _, row in feat_df.iterrows():
            top1_vals = [row.get(f) for f in top1_art["features"]]
            bot1_vals = [row.get(f) for f in bot1_art["features"]]

            if _has_missing(top1_vals) or _has_missing(bot1_vals):
                missing = [f for f, v in zip(top1_art["features"] + bot1_art["features"],
                                              top1_vals + bot1_vals)
                           if v is None or (isinstance(v, float) and np.isnan(v))]
                dropped.append({"game_pk": row["game_pk"], "home_team": row["home_team"],
                                "away_team": row["away_team"],
                                "drop_reason": f"missing_features:{','.join(missing[:3])}"})
                continue

            x_t = pd.DataFrame([top1_vals], columns=top1_art["features"])
            x_b = pd.DataFrame([bot1_vals], columns=bot1_art["features"])
            p_top1 = float(top1_art["model"].predict_proba(top1_art["scaler"].transform(x_t))[0, 1])
            p_bot1 = float(bot1_art["model"].predict_proba(bot1_art["scaler"].transform(x_b))[0, 1])
            p_yrfi = 1 - (1 - p_top1) * (1 - p_bot1)

            # Classify home starter archetype for Phase 8 overlay
            _gobj = row.get("_game")
            home_sp_id = None
            if isinstance(_gobj, dict):
                home_sp_id = _gobj.get("home_probable_pitcher", {}).get("id")
            home_arch = _classify_starter_archetype(home_sp_id, pgl, sc_ps, arch_art)

            scored.append({
                "game_pk": row["game_pk"],
                "home_team": row["home_team"],
                "away_team": row["away_team"],
                "p_top1": p_top1,
                "p_bot1": p_bot1,
                "p_yrfi": p_yrfi,
                "home_starter_archetype": home_arch,
            })

    slate_size = len(scored) + len(dropped)
    now = datetime.now(timezone.utc).isoformat()
    new_entries = []

    # Scored games — compute ranks and qualification
    if scored:
        scored_df = pd.DataFrame(scored)
        scored_df["combined_rank_pct"] = scored_df["p_yrfi"].rank(pct=True)
        scored_df["top1_rank_pct"] = scored_df["p_top1"].rank(pct=True)
        scored_df["bot1_rank_pct"] = scored_df["p_bot1"].rank(pct=True)

        b10_cut = scored_df["p_yrfi"].quantile(0.10)
        top1_b30_cut = scored_df["p_top1"].quantile(0.30)
        bot1_b30_cut = scored_df["p_bot1"].quantile(0.30)

        # Phase 4 Rule D
        scored_df["qualifies_phase4"] = (
            (scored_df["p_yrfi"] <= b10_cut) &
            (scored_df["p_top1"] <= top1_b30_cut) &
            (scored_df["p_bot1"] <= bot1_b30_cut)
        )

        # Phase 8 overlay: Phase 4 AND home starter is NOT CONTACT_RISK
        scored_df["qualifies_phase8"] = (
            scored_df["qualifies_phase4"] &
            (scored_df["home_starter_archetype"] != "CONTACT_RISK")
        )
        # If archetype is null (missing data), keep Phase 4 qualification as-is
        scored_df.loc[scored_df["home_starter_archetype"].isna(), "qualifies_phase8"] = (
            scored_df.loc[scored_df["home_starter_archetype"].isna(), "qualifies_phase4"]
        )

        for _, r in scored_df.iterrows():
            new_entries.append({
                "date": game_date,
                "logged_at": now,
                "slate_size": slate_size,
                "game_id": str(r["game_pk"]),
                "away_team": r["away_team"],
                "home_team": r["home_team"],
                "p_top1_run": round(r["p_top1"], 4),
                "p_bot1_run": round(r["p_bot1"], 4),
                "p_yrfi": round(r["p_yrfi"], 4),
                "combined_rank_pct": round(r["combined_rank_pct"], 3),
                "top1_rank_pct": round(r["top1_rank_pct"], 3),
                "bot1_rank_pct": round(r["bot1_rank_pct"], 3),
                "home_starter_archetype": r.get("home_starter_archetype"),
                "qualifies": bool(r["qualifies_phase8"]),
                "qualifies_phase4": bool(r["qualifies_phase4"]),
                "qualifies_phase8": bool(r["qualifies_phase8"]),
                "result_yrfi": None,
                "result_nrfi": None,
                "resolved": False,
            })

    # Dropped games — log with nulls and drop reason
    for d in dropped:
        new_entries.append({
            "date": game_date,
            "logged_at": now,
            "slate_size": slate_size,
            "game_id": str(d["game_pk"]),
            "away_team": d["away_team"],
            "home_team": d["home_team"],
            "p_top1_run": None,
            "p_bot1_run": None,
            "p_yrfi": None,
            "combined_rank_pct": None,
            "top1_rank_pct": None,
            "bot1_rank_pct": None,
            "home_starter_archetype": None,
            "qualifies": False,
            "qualifies_phase4": False,
            "qualifies_phase8": False,
            "drop_reason": d["drop_reason"],
            "result_yrfi": None,
            "result_nrfi": None,
            "resolved": False,
        })

    log.extend(new_entries)
    with open(SHADOW_LOG, "w") as f:
        json.dump(log, f, indent=2)

    q_p4 = [e for e in new_entries if e.get("qualifies_phase4")]
    q_p8 = [e for e in new_entries if e.get("qualifies_phase8")]
    excluded = [e for e in new_entries if e.get("qualifies_phase4") and not e.get("qualifies_phase8")]
    print(f"NRFI Helper — {game_date}")
    print(f"  Slate: {len(scored)} scored, {len(dropped)} dropped ({slate_size} total)")
    print(f"  Phase 4 qualifiers: {len(q_p4)}")
    print(f"  Phase 8 qualifiers: {len(q_p8)}")
    if excluded:
        for e in excluded:
            print(f"    EXCLUDED (home CONTACT_RISK): {e['away_team']}@{e['home_team']} "
                  f"arch={e.get('home_starter_archetype')}")
    if dropped:
        for d in dropped:
            print(f"    DROPPED: {d['away_team']}@{d['home_team']} — {d['drop_reason']}")
    for q in q_p8:
        print(f"    {q['away_team']}@{q['home_team']}  p_yrfi={q['p_yrfi']:.4f}  "
              f"rank={q['combined_rank_pct']:.3f}  home_arch={q.get('home_starter_archetype')}")

    # Auto-push
    subprocess.run(["bash", str(PROJECT_ROOT / "shared" / "git_push.sh"),
                    f"NRFI helper {game_date}"], capture_output=True)


# ── Grading ──────────────────────────────────────────────────────────────────

def grade():
    if not SHADOW_LOG.exists():
        print("No shadow log found.")
        return

    log = json.load(open(SHADOW_LOG))
    unresolved = [e for e in log if not e.get("resolved")]
    if not unresolved:
        print("No unresolved entries.")
        return

    print(f"Grading {len(unresolved)} unresolved entries...")
    graded = 0

    for entry in log:
        if entry.get("resolved"):
            continue

        game_pk = int(entry["game_id"])

        try:
            # Check if game is final
            sched = requests.get(f"{MLB_API}/schedule", params={"gamePk": game_pk}, timeout=10)
            sched.raise_for_status()
            status = None
            for d in sched.json().get("dates", []):
                for g in d.get("games", []):
                    if g.get("gamePk") == game_pk:
                        status = g.get("status", {}).get("abstractGameState")
                        break

            if status != "Final":
                continue

            # Fetch linescore
            ls = requests.get(f"{MLB_API}/game/{game_pk}/linescore", timeout=10)
            ls.raise_for_status()
            innings = ls.json().get("innings", [])

            if not innings:
                continue

            inn1 = innings[0]
            away_r1 = inn1.get("away", {}).get("runs")
            home_r1 = inn1.get("home", {}).get("runs")

            if away_r1 is None or home_r1 is None:
                continue

            yrfi = 1 if (away_r1 + home_r1) > 0 else 0
            entry["result_yrfi"] = yrfi
            entry["result_nrfi"] = 1 - yrfi
            entry["resolved"] = True
            graded += 1

            print(f"  {entry['away_team']}@{entry['home_team']} ({entry['date']}): "
                  f"top1={away_r1} bot1={home_r1} → {'YRFI' if yrfi else 'NRFI'}")

        except Exception as e:
            print(f"  {entry['game_id']}: error — {e}")
            continue

    with open(SHADOW_LOG, "w") as f:
        json.dump(log, f, indent=2)

    print(f"Graded {graded} entries.")

    # Summary
    resolved = [e for e in log if e.get("resolved")]
    if resolved:
        quals = [e for e in resolved if e.get("qualifies")]
        all_nrfi = sum(1 for e in resolved if e.get("result_nrfi") == 1) / len(resolved)
        qual_nrfi = (sum(1 for e in quals if e.get("result_nrfi") == 1) / len(quals)) if quals else 0
        print(f"\n  Tracker: {len(resolved)} resolved, {len(quals)} qualifiers resolved")
        print(f"  Full-slate NRFI: {all_nrfi:.1%}")
        print(f"  Qualifier NRFI:  {qual_nrfi:.1%}")

    # Auto-push
    subprocess.run(["bash", str(PROJECT_ROOT / "shared" / "git_push.sh"),
                    "NRFI grader run"], capture_output=True)


# ── Entry point ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NRFI Parlay Helper")
    parser.add_argument("--date", default=None, help="Game date YYYY-MM-DD")
    parser.add_argument("--grade", action="store_true", help="Grade unresolved entries")
    args = parser.parse_args()

    if args.grade:
        grade()
    else:
        run_daily(args.date)
