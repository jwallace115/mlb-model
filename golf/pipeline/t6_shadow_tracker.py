#!/usr/bin/env python3
"""
Golf H2H Fade Shadow Tracker
=============================
Tracks two golfer subtypes in 72-hole H2H markets:
  T7 (primary): weak BS, heavy putting dependence, weak cut survival
  T3 (secondary): modest BS, low putting dep, low volatility, weak cut survival
Fade = bet the opponent when a tracked-type player is near-even priced.

Usage:
  python golf/pipeline/t6_shadow_tracker.py --mode capture
  python golf/pipeline/t6_shadow_tracker.py --mode grade
  python golf/pipeline/t6_shadow_tracker.py --mode report
"""

import argparse
import hashlib
import json
import os
import pickle
import sys
from datetime import datetime, date
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

# ── Paths ────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent.parent
SHADOW_DIR = ROOT / "golf" / "research" / "t6_shadow"
LOG_PATH = SHADOW_DIR / "shadow_log_2026.json"
MODEL_PATH = SHADOW_DIR / "kmeans_model.pkl"
SCALER_PATH = SHADOW_DIR / "scaler.pkl"
META_PATH = SHADOW_DIR / "taxonomy_meta.json"
STATUS_PATH = SHADOW_DIR / "shadow_status.json"
DG_ROUNDS_PATH = ROOT / "golf" / "data" / "canonical" / "dg_rounds_expanded.parquet"
BDL_PRR_PATH = ROOT / "golf" / "data" / "canonical" / "bdl" / "player_round_results.parquet"
ENV_PATH = ROOT / ".env"

# ── Taxonomy config ──────────────────────────────────────────────────────────
AXES = ["bs", "putt_dep", "par5_tilt", "vol", "cut_rate"]
N_CLUSTERS = 8
RANDOM_STATE = 42
N_INIT = 20
FADE_IMPLIED_LO = 0.30
FADE_IMPLIED_HI = 0.70
MIN_ROUNDS_FOR_CARD = 8
CARD_WINDOW = 16

# ── Tracked subtypes ─────────────────────────────────────────────────────────
# type_id from taxonomy_meta.json → label, historical baseline residual
TRACKED_TYPES = {
    7: {"label": "T7", "role": "primary", "historical_residual": -5.1,
        "description": "weak BS, heavy putting dep, weak cut survival"},
    3: {"label": "T3", "role": "secondary", "historical_residual": -2.2,
        "description": "modest BS, low putting dep, low vol, weak cut survival"},
}
TRACKED_TYPE_IDS = set(TRACKED_TYPES.keys())
TRACKED_LABELS = {v["label"] for v in TRACKED_TYPES.values()}


def load_env():
    if ENV_PATH.exists():
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip("'\"")


def load_dg_rounds():
    df = pd.read_parquet(DG_ROUNDS_PATH)
    df["event_date"] = pd.to_datetime(df["event_completed"], errors="coerce")
    df = df[df["sg_putt"].notna() & df["event_date"].notna()].copy()
    df["sg_t2g"] = df["sg_ott"].fillna(0) + df["sg_app"].fillna(0) + df["sg_arg"].fillna(0)
    return df


def build_card(player_rounds, cutoff_date):
    prior = player_rounds[player_rounds["event_date"] < cutoff_date]
    if len(prior) < MIN_ROUNDS_FOR_CARD:
        return None
    r = prior.tail(CARD_WINDOW)
    bs = r["sg_t2g"].mean()
    putt_dep = r["sg_putt"].mean() - r["sg_t2g"].mean()
    eagle_rate = r["eagles_or_better"].fillna(0).mean() if "eagles_or_better" in r.columns else 0
    vol = r["score"].std() if r["score"].notna().sum() > 1 else np.nan
    evt = prior.groupby("event_id").agg(n_rounds=("round_num", "nunique")).reset_index()
    recent = evt.tail(8)
    cut_rate = (recent["n_rounds"] >= 3).mean() if len(recent) > 0 else np.nan
    if np.isnan(vol) or np.isnan(cut_rate):
        return None
    return {"bs": bs, "putt_dep": putt_dep, "par5_tilt": eagle_rate,
            "vol": vol, "cut_rate": cut_rate}


def rebuild_taxonomy(dg_sg):
    print("  Rebuilding taxonomy from DG rounds...")
    cards = []
    for pid in dg_sg["dg_id"].unique():
        pr = dg_sg[dg_sg["dg_id"] == pid].sort_values("event_date")
        if len(pr) < MIN_ROUNDS_FOR_CARD:
            continue
        for eid in pr["event_id"].unique():
            evt_date = pr[pr["event_id"] == eid]["event_date"].iloc[0]
            card = build_card(pr, evt_date)
            if card:
                cards.append({"pid": pid, "eid": eid, **card})
    df = pd.DataFrame(cards)
    print(f"  Built {len(df)} cards from {df['pid'].nunique()} players")
    scaler = StandardScaler()
    X = scaler.fit_transform(df[AXES])
    km = KMeans(n_clusters=N_CLUSTERS, random_state=RANDOM_STATE, n_init=N_INIT)
    km.fit(X)
    df["raw_type"] = km.predict(X)
    type_bs = df.groupby("raw_type")["bs"].mean().sort_values(ascending=False)
    remap = {old: i for i, old in enumerate(type_bs.index)}
    df["type_id"] = df["raw_type"].map(remap)
    profiles = df.groupby("type_id").agg(
        bs=("bs", "mean"), putt_dep=("putt_dep", "mean"), cut_rate=("cut_rate", "mean")
    ).reset_index()
    profiles["score"] = -profiles["bs"] + profiles["putt_dep"] - profiles["cut_rate"]
    t6_id = int(profiles.loc[profiles["score"].idxmax(), "type_id"])
    SHADOW_DIR.mkdir(parents=True, exist_ok=True)
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(km, f)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)
    meta = {
        "n_clusters": N_CLUSTERS, "axes": AXES,
        "type_remap": {str(k): int(v) for k, v in remap.items()},
        "t6_type_id": t6_id,
        "t6_profile": profiles[profiles["type_id"] == t6_id].iloc[0][["bs", "putt_dep", "cut_rate"]].to_dict(),
        "rebuilt_at": datetime.utcnow().isoformat(),
    }
    with open(META_PATH, "w") as f:
        json.dump(meta, f, indent=2, default=float)
    print(f"  Saved: {MODEL_PATH.name}, {SCALER_PATH.name}, {META_PATH.name}")
    return km, scaler, meta


def load_taxonomy(dg_sg=None):
    if MODEL_PATH.exists() and SCALER_PATH.exists() and META_PATH.exists():
        with open(MODEL_PATH, "rb") as f:
            km = pickle.load(f)
        with open(SCALER_PATH, "rb") as f:
            scaler = pickle.load(f)
        with open(META_PATH) as f:
            meta = json.load(f)
        print(f"  Loaded taxonomy — tracked types: {list(TRACKED_TYPES.keys())}")
        return km, scaler, meta
    else:
        if dg_sg is None:
            dg_sg = load_dg_rounds()
        return rebuild_taxonomy(dg_sg)


def classify_player(dg_sg, dg_id, cutoff_date, km, scaler, meta):
    pr = dg_sg[dg_sg["dg_id"] == dg_id].sort_values("event_date")
    card = build_card(pr, cutoff_date)
    if card is None:
        return "INSUFFICIENT_HISTORY", None, None
    X = scaler.transform(pd.DataFrame([card])[AXES])
    raw_type = km.predict(X)[0]
    remap = {int(k): v for k, v in meta["type_remap"].items()}
    type_id = remap.get(raw_type, raw_type)
    return f"T{type_id}", card, type_id


def load_shadow_log():
    if LOG_PATH.exists():
        with open(LOG_PATH) as f:
            data = json.load(f)
        # Backfill legacy entries missing tracked_type
        changed = False
        for e in data:
            if "tracked_type" not in e or e["tracked_type"] is None:
                e["tracked_type"] = "T7"
                changed = True
            if "historical_residual_baseline" not in e or e["historical_residual_baseline"] is None:
                e["historical_residual_baseline"] = -5.1
                changed = True
        if changed:
            save_shadow_log(data)
        return data
    return []


def save_shadow_log(entries):
    SHADOW_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "w") as f:
        json.dump(entries, f, indent=2, default=str)


def make_entry_id(event_name, p1_id, p2_id, market):
    raw = f"{event_name}_{p1_id}_{p2_id}_{market}"
    return hashlib.md5(raw.encode()).hexdigest()[:16]


# ── MODE: CAPTURE ────────────────────────────────────────────────────────────

def run_capture():
    print("Golf H2H Fade Shadow Tracker — CAPTURE")
    print("=" * 50)

    load_env()
    dg_key = os.environ.get("DATAGOLF_API_KEY")
    if not dg_key:
        print("ERROR: DATAGOLF_API_KEY not found in .env")
        sys.exit(1)

    dg_sg = load_dg_rounds()
    km, scaler, meta = load_taxonomy(dg_sg)

    print("\n  Calling DataGolf matchups API...")
    try:
        r = requests.get("https://feeds.datagolf.com/betting-tools/matchups",
                         params={"market": "tournament_matchups", "tour": "pga",
                                 "file_format": "json", "key": dg_key},
                         timeout=30)
    except Exception as e:
        print(f"  API error: {e}")
        sys.exit(1)

    if not r.ok:
        print(f"  API returned {r.status_code}: {r.text[:200]}")
        sys.exit(1)

    data = r.json()
    event_name = data.get("event_name", "unknown")
    last_updated = data.get("last_updated", "")
    match_list = data.get("match_list", [])

    print(f"  Event: {event_name}")
    print(f"  Last updated: {last_updated}")

    if isinstance(match_list, str) or not match_list:
        print("  No tournament_matchups available — likely mid-event. Try Wednesday.")
        sys.exit(0)

    print(f"  Matchups found: {len(match_list)}")

    for i, m in enumerate(match_list[:2]):
        print(f"\n  Raw record {i}: {json.dumps(m, indent=2, default=str)[:400]}")

    cutoff = pd.Timestamp(datetime.utcnow())
    existing = load_shadow_log()
    existing_ids = {e["entry_id"] for e in existing}
    new_entries = []
    found_by_type = {v["label"]: [] for v in TRACKED_TYPES.values()}
    skipped_both_tracked = 0

    for m in match_list:
        p1_id = m.get("p1_dg_id")
        p2_id = m.get("p2_dg_id")
        p1_name = m.get("p1_player_name", "?")
        p2_name = m.get("p2_player_name", "?")

        odds = m.get("odds", {})
        pin = odds.get("pinnacle", {})
        if not pin or not pin.get("p1") or not pin.get("p2"):
            continue

        p1_dec = pin["p1"]
        p2_dec = pin["p2"]
        p1_imp = 1 / p1_dec if p1_dec > 0 else None
        p2_imp = 1 / p2_dec if p2_dec > 0 else None
        if p1_imp is None or p2_imp is None:
            continue

        dg_model = odds.get("datagolf", {})
        dg_p1 = 1 / dg_model["p1"] if dg_model.get("p1") and dg_model["p1"] > 0 else None
        dg_p2 = 1 / dg_model["p2"] if dg_model.get("p2") and dg_model["p2"] > 0 else None

        p1_label, p1_card, p1_tid = classify_player(dg_sg, p1_id, cutoff, km, scaler, meta)
        p2_label, p2_card, p2_tid = classify_player(dg_sg, p2_id, cutoff, km, scaler, meta)

        # Skip if both are tracked types
        p1_tracked = p1_label in TRACKED_LABELS
        p2_tracked = p2_label in TRACKED_LABELS
        if p1_tracked and p2_tracked:
            skipped_both_tracked += 1
            continue

        # Check each side for fade opportunity
        for trk_pid, trk_name, trk_label, trk_card, trk_tid, trk_imp, trk_dec, trk_dg, \
            opp_pid, opp_name, opp_label, opp_imp, opp_dec, opp_dg in [
            (p1_id, p1_name, p1_label, p1_card, p1_tid, p1_imp, p1_dec, dg_p1,
             p2_id, p2_name, p2_label, p2_imp, p2_dec, dg_p2),
            (p2_id, p2_name, p2_label, p2_card, p2_tid, p2_imp, p2_dec, dg_p2,
             p1_id, p1_name, p1_label, p1_imp, p1_dec, dg_p1),
        ]:
            if trk_label not in TRACKED_LABELS:
                continue
            if opp_label == "INSUFFICIENT_HISTORY":
                continue
            if opp_label in TRACKED_LABELS:
                continue
            if not (FADE_IMPLIED_LO <= trk_imp <= FADE_IMPLIED_HI):
                continue

            tracked_info = TRACKED_TYPES.get(trk_tid, {})
            found_by_type.get(trk_label, []).append(trk_name)

            if trk_imp > 0.55:
                band = f"{trk_label}_favorite"
            elif trk_imp < 0.45:
                band = f"{trk_label}_underdog"
            else:
                band = "near_even"

            eid = make_entry_id(event_name, trk_pid, opp_pid, "tournament_matchups")
            if eid in existing_ids:
                continue

            entry = {
                "entry_id": eid,
                "event_name": event_name,
                "captured_at": datetime.utcnow().isoformat(),
                "last_updated": last_updated,
                "market": "tournament_matchups",
                "ties_rule": m.get("ties", "void"),
                "tracked_type": trk_label,
                "historical_residual_baseline": tracked_info.get("historical_residual"),
                "t6_player_name": trk_name,
                "t6_player_dg_id": int(trk_pid),
                "t6_player_cluster": trk_label,
                "t6_player_axes": {
                    "ball_striking": round(trk_card["bs"], 4),
                    "putt_dep": round(trk_card["putt_dep"], 4),
                    "cut_rate": round(trk_card["cut_rate"], 4),
                } if trk_card else None,
                "opponent_name": opp_name,
                "opponent_dg_id": int(opp_pid),
                "opponent_cluster": opp_label,
                "t6_pinnacle_decimal": round(trk_dec, 4),
                "opponent_pinnacle_decimal": round(opp_dec, 4),
                "t6_implied_prob": round(trk_imp, 4),
                "opponent_implied_prob": round(opp_imp, 4),
                "datagolf_model_prob_t6": round(trk_dg, 4) if trk_dg else None,
                "datagolf_model_prob_opponent": round(opp_dg, 4) if opp_dg else None,
                "fade_direction": f"bet {opp_name} to beat {trk_name}",
                "t6_price_band": band,
                "result": None,
                "settled_date": None,
                "voided": False,
            }
            new_entries.append(entry)
            existing_ids.add(eid)

    all_entries = existing + new_entries
    save_shadow_log(all_entries)

    print(f"\n  Tracked players identified:")
    for lbl, names in found_by_type.items():
        if names:
            print(f"    {lbl}: {list(set(names))}")
    print(f"  Skipped (both tracked): {skipped_both_tracked}")
    print(f"  New fade opportunities: {len(new_entries)}")
    print(f"  Total shadow log entries: {len(all_entries)}")
    print(f"  Log: {LOG_PATH}")


# ── MODE: GRADE ──────────────────────────────────────────────────────────────

def run_grade():
    print("Golf H2H Fade Shadow Tracker — GRADE")
    print("=" * 50)

    entries = load_shadow_log()
    if not entries:
        print("  No entries to grade.")
        return

    pending = [e for e in entries if e.get("result") is None and not e.get("voided")]
    if not pending:
        print("  No pending entries.")
        return

    print(f"  Pending entries: {len(pending)}")

    if BDL_PRR_PATH.exists():
        prr = pd.read_parquet(BDL_PRR_PATH)
    else:
        print(f"  WARNING: {BDL_PRR_PATH} not found — cannot grade")
        return

    outcomes = prr.groupby(["tournament_id", "player_id"]).agg(
        total_par=("par_relative_score", "sum"),
        rounds_played=("round_number", "nunique"),
    ).reset_index()

    graded = 0
    for entry in entries:
        if entry.get("result") is not None or entry.get("voided"):
            continue

        trk_id = entry["t6_player_dg_id"]
        opp_id = entry["opponent_dg_id"]

        trk_scores = outcomes[outcomes["player_id"] == trk_id]
        opp_scores = outcomes[outcomes["player_id"] == opp_id]

        shared = set(trk_scores["tournament_id"]) & set(opp_scores["tournament_id"])
        if not shared:
            continue

        for tid in shared:
            trk_total = trk_scores[trk_scores["tournament_id"] == tid]["total_par"].iloc[0]
            opp_total = opp_scores[opp_scores["tournament_id"] == tid]["total_par"].iloc[0]

            if opp_total < trk_total:
                entry["result"] = "WIN"
            elif opp_total > trk_total:
                entry["result"] = "LOSS"
            else:
                entry["result"] = "VOID"
                entry["voided"] = True

            entry["settled_date"] = datetime.utcnow().isoformat()
            graded += 1
            ttype = entry.get("tracked_type", "T7")
            print(f"  Graded [{ttype}]: {entry['t6_player_name']} vs {entry['opponent_name']} "
                  f"→ {entry['result']}")
            break

    save_shadow_log(entries)
    print(f"\n  Newly graded: {graded}")


# ── MODE: REPORT ─────────────────────────────────────────────────────────────

def _report_type(entries, type_label):
    """Print report for a single tracked type."""
    typed = [e for e in entries if e.get("tracked_type") == type_label]
    pending = [e for e in typed if e.get("result") is None and not e.get("voided")]
    settled = [e for e in typed if e.get("result") in ("WIN", "LOSS")]
    voided = [e for e in typed if e.get("voided")]

    info = next((v for v in TRACKED_TYPES.values() if v["label"] == type_label), {})
    baseline = info.get("historical_residual", "?")

    print(f"\n=== {type_label} FADE REPORT ({info.get('role','')}) ===")
    print(f"  Historical baseline: {baseline}pp")
    print(f"  Total: {len(typed)}  Pending: {len(pending)}  Voided: {len(voided)}")

    if not settled:
        print(f"  Settled: 0 — no results yet")
        print(f"  Review gate: 25 settled before go/no-go")
        return

    wins = sum(1 for e in settled if e["result"] == "WIN")
    losses = sum(1 for e in settled if e["result"] == "LOSS")
    hit = wins / len(settled)
    avg_imp = np.mean([e.get("opponent_implied_prob", 0.5) for e in settled])
    edge = (hit - avg_imp) * 100

    net = 0
    for e in settled:
        dec = e.get("opponent_pinnacle_decimal", 2.0)
        if e["result"] == "WIN":
            net += dec - 1
        else:
            net -= 1
    roi = net / len(settled) * 100

    print(f"  Settled: {wins}W-{losses}L ({len(settled)} total)")
    print(f"  Hit rate: {hit*100:.1f}%")
    print(f"  Avg opponent implied: {avg_imp*100:.1f}%")
    print(f"  Edge: {edge:+.1f}pp")
    print(f"  ROI (flat stake): {roi:+.1f}%")
    print(f"  Review gate: {len(settled)}/25 settled")

    for e in settled:
        print(f"    {e['event_name']:30s} | {e['t6_player_name']:20s} vs {e['opponent_name']:20s} "
              f"| {e['result']:4s}")


def run_report():
    print("Golf H2H Fade Shadow Tracker — REPORT")
    print("=" * 50)

    entries = load_shadow_log()
    if not entries:
        print("  Shadow log empty.")
        return

    for ttype in TRACKED_TYPES.values():
        _report_type(entries, ttype["label"])

    # Combined summary
    print(f"\n=== COMBINED SUMMARY ===")
    print(f"  Total entries: {len(entries)}")
    pending = sum(1 for e in entries if e.get("result") is None and not e.get("voided"))
    settled = sum(1 for e in entries if e.get("result") in ("WIN", "LOSS"))
    print(f"  Pending: {pending}  Settled: {settled}")
    for ttype in TRACKED_TYPES.values():
        lbl = ttype["label"]
        n = sum(1 for e in entries if e.get("tracked_type") == lbl and e.get("result") in ("WIN","LOSS"))
        print(f"    {lbl}: {n} settled")


# ── MAIN ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Golf H2H Fade Shadow Tracker")
    parser.add_argument("--mode", required=True, choices=["capture", "grade", "report"])
    args = parser.parse_args()

    if args.mode == "capture":
        run_capture()
    elif args.mode == "grade":
        run_grade()
    elif args.mode == "report":
        run_report()
