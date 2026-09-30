#!/usr/bin/env python3
"""
FWD1 (D211/D215): forward-test harness for the frozen NFL sim v1.

Usage:
  python3 nfl/sim/run_forward_v1.py --week 3 [--pilot] [--as-of ...] [--window-hours 9] [--events pit,cle]
"""

import argparse, hashlib, json, os, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

READER_MODEL = "nfl_sim_v1_156cd057"
SEASON = 2026
ANCHOR_MISS_TOL = 1.0
GAME_MARKETS = ("h2h", "spreads", "totals")
# D215(a)/D220: explicit family -> sheet market_key map; unlisted families are not matched.
FAMILY_TO_MARKET = {
    "receptions": "player_receptions",
    "rush_attempts": "player_rush_attempts",
}

EXPERIMENT_MANIFEST = ROOT / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json"
PROPS_DIR = ROOT / "data" / "odds_archive" / "nfl" / "props"
LINES_DIR = ROOT / "data" / "odds_archive" / "nfl" / "line_history"
BOARD_ROOT = ROOT / "nfl" / "data" / "board"
BOOK = "hardrockbet_fl"
QUOTE_MAX_AGE_H = 3.0  # HALT if any event's newest props pull is older than this at T


# ── D225: immutable run bundle ───────────────────────────────────────────────

def _parse_utc(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _load_props_at_T(season, T):
    """Load HR props with newest pull ≤ T per event, from archive + manual/."""
    season_dir = PROPS_DIR / f"season={season}"
    if not season_dir.exists():
        return pd.DataFrame()
    files = sorted(season_dir.glob("month=*/data_*.parquet"))
    manual_dir = season_dir / "manual"
    if manual_dir.exists():
        files += sorted(manual_dir.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    dfs = [pd.read_parquet(f) for f in files]
    props = pd.concat(dfs, ignore_index=True)
    props = props[props["bookmaker"] == BOOK]
    # Only pre-kick pulls that are ≤ T
    props = props[props["pull_timestamp"].map(_parse_utc) <= T]
    props = props[props["pull_timestamp"].map(_parse_utc) < props["commence_time"].map(_parse_utc)]
    # Newest pull per event
    if props.empty:
        return props
    newest = props.groupby("event_id")["pull_timestamp"].transform("max")
    return props[props["pull_timestamp"] == newest].copy()


def _load_lines_at_T(season, T):
    """Load HR game lines with newest snapshot ≤ T."""
    season_dir = LINES_DIR / f"season={season}"
    if not season_dir.exists():
        raise SystemExit("HALT: no game-line snapshots for the season")
    snaps = sorted(season_dir.glob("snap_*.parquet"))
    if not snaps:
        raise SystemExit("HALT: no game-line snapshots for the season")
    # Filter snapshots by timestamp in filename or content
    candidates = []
    for s in snaps:
        df = pd.read_parquet(s)
        if df.empty:
            continue
        snap_utc = _parse_utc(df["snapshot_utc"].iloc[0])
        if snap_utc <= T:
            candidates.append((snap_utc, df))
    if not candidates:
        raise SystemExit("HALT: no game-line snapshot ≤ T")
    # Take the newest snapshot ≤ T
    candidates.sort(key=lambda x: x[0])
    _, lines = candidates[-1]
    return lines[lines["bookmaker"] == BOOK].copy()


def build_bundle(season, week, T, pilot=False, allow_stale_quotes=False,
                 window_hours=None, event_filter=None, _root=None):
    """D225: build an immutable run bundle at cutoff T.

    Returns (bundle_dir, bundle_manifest) and writes:
      - events.parquet (event list for the window)
      - props.parquet (HR props, newest pull ≤ T per event)
      - lines.parquet (HR game lines, newest snapshot ≤ T)
      - freshness.json (input freshness)
      - bundle_manifest.json (sha256 of every file)
    """
    from nfl.sim.names import FULL_TO_ABBR

    run_id = T.strftime("%Y%m%dT%H%M%SZ")
    bundle_dir = (BOARD_ROOT / f"week={season}_{week:02d}" /
                  "sim_runs" / run_id)
    bundle_dir.mkdir(parents=True, exist_ok=True)

    # ── props ──
    props = _load_props_at_T(season, T)
    # Only pre-kick events
    if not props.empty:
        props = props[props["commence_time"].map(_parse_utc) > T]

    # ── lines ──
    lines = _load_lines_at_T(season, T)
    if not lines.empty:
        lines = lines[lines["commence_time"].map(_parse_utc) > T]

    # ── event list from props + lines ──
    event_ids = set()
    event_rows = []
    for df, label in [(props, "props"), (lines, "lines")]:
        if df.empty:
            continue
        for eid in df["event_id"].unique():
            if eid in event_ids:
                continue
            event_ids.add(eid)
            row = df[df["event_id"] == eid].iloc[0]
            home_full = row["home_team"]
            away_full = row["away_team"]
            home_abbr = FULL_TO_ABBR.get(home_full, home_full)
            away_abbr = FULL_TO_ABBR.get(away_full, away_full)
            event_rows.append({
                "event_id": eid,
                "home_team": home_full, "away_team": away_full,
                "home_abbr": home_abbr, "away_abbr": away_abbr,
                "game_id": f"{away_abbr}@{home_abbr}",
                "commence_time": row["commence_time"],
            })
    events = pd.DataFrame(event_rows)

    # ── filters ──
    if event_filter and not events.empty:
        fr = [x.strip().lower() for x in event_filter.split(",")]
        mask = events.apply(
            lambda r: any(x in (r["home_team"] + " " + r["away_team"]).lower() for x in fr),
            axis=1)
        events = events[mask]
        eids = set(events["event_id"])
        if not props.empty:
            props = props[props["event_id"].isin(eids)]
        if not lines.empty:
            lines = lines[lines["event_id"].isin(eids)]

    if window_hours and not events.empty:
        hrs = events["commence_time"].map(lambda c: (_parse_utc(c) - T).total_seconds() / 3600)
        events = events[hrs <= window_hours]
        eids = set(events["event_id"])
        if not props.empty:
            props = props[props["event_id"].isin(eids)]
        if not lines.empty:
            lines = lines[lines["event_id"].isin(eids)]

    if events.empty:
        raise SystemExit("HALT: no pre-kick events in the window")

    # ── quote-age check ──
    if not props.empty:
        props_age = props.groupby("event_id")["pull_timestamp"].first().map(
            lambda t: (T - _parse_utc(t)).total_seconds() / 3600)
        oldest = props_age.max()
        if oldest > QUOTE_MAX_AGE_H and not (pilot and allow_stale_quotes):
            raise SystemExit(
                f"HALT: props pull is {oldest:.1f}h old for event "
                f"{props_age.idxmax()} (max allowed: {QUOTE_MAX_AGE_H}h). "
                f"Pilot may override with --allow-stale-quotes.")

    # ── freshness ──
    freshness = {"cutoff_T": T.isoformat(), "run_id": run_id}
    # Check ratings max week
    _r = _root or ROOT
    ratings_dir = _r / "nfl" / "data" / "sim" / "ratings"
    for fname, label in [("team_ratings_weekly.parquet", "team_ratings"),
                         ("tendencies_weekly.parquet", "tendencies"),
                         ("player_usage_weekly.parquet", "usage")]:
        fpath = ratings_dir / fname
        if fpath.exists():
            rdf = pd.read_parquet(fpath, columns=["season", "week"])
            max_w = int(rdf[rdf["season"] == season]["week"].max()) if len(rdf[rdf["season"] == season]) else 0
            freshness[f"{label}_max_week"] = max_w
        else:
            freshness[f"{label}_max_week"] = None
    # Kickers: documented fallback if no 2026 rows
    kicker_path = ratings_dir / "kicker_ratings.parquet"
    if kicker_path.exists():
        kdf = pd.read_parquet(kicker_path, columns=["season"])
        if season in kdf["season"].values:
            freshness["kickers"] = "current_season"
        else:
            freshness["kickers"] = "engine_default_fallback"
    else:
        freshness["kickers"] = "missing"

    # ── write ──
    events.to_parquet(bundle_dir / "events.parquet", index=False)
    props.to_parquet(bundle_dir / "props.parquet", index=False)
    lines.to_parquet(bundle_dir / "lines.parquet", index=False)
    (bundle_dir / "freshness.json").write_text(json.dumps(freshness, indent=1) + "\n")

    # ── sha256 manifest ──
    manifest = {}
    for fname in ["events.parquet", "props.parquet", "lines.parquet", "freshness.json"]:
        fpath = bundle_dir / fname
        manifest[fname] = hashlib.sha256(fpath.read_bytes()).hexdigest()
    manifest["pilot"] = pilot
    manifest["allow_stale_quotes"] = allow_stale_quotes
    (bundle_dir / "bundle_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")

    print(f"  Bundle: {bundle_dir.relative_to(_r)}")
    print(f"  Events: {len(events)}, Props: {len(props)}, Lines: {len(lines)}")
    for k, v in freshness.items():
        if k not in ("cutoff_T", "run_id"):
            print(f"  {k}: {v}")

    return bundle_dir, manifest


def lines_dict_from_bundle(bundle_dir):
    """D226: build {game_id: {"spread": ..., "total": ...}} from the bundle's lines."""
    from nfl.sim.names import FULL_TO_ABBR
    lines = pd.read_parquet(bundle_dir / "lines.parquet")
    events = pd.read_parquet(bundle_dir / "events.parquet")
    eid_to_gid = dict(zip(events["event_id"], events["game_id"]))
    result = {}
    for eid, gdf in lines.groupby("event_id"):
        gid = eid_to_gid.get(eid)
        if not gid:
            continue
        spreads = gdf[gdf["market"] == "spreads"]
        totals = gdf[gdf["market"] == "totals"]
        if spreads.empty or totals.empty:
            continue
        # Home team spread: the point for the home team's outcome
        home_full = gdf["home_team"].iloc[0]
        home_sp = spreads[spreads["outcome_name"].apply(
            lambda x: home_full.split()[-1] in str(x) if x else False)]
        spread = -float(home_sp["point"].iloc[0]) if not home_sp.empty else None
        over = totals[totals["outcome_name"] == "Over"]
        total = float(over["point"].iloc[0]) if not over.empty else None
        if spread is not None and total is not None:
            result[gid] = {"spread": spread, "total": total}
    return result


def check_experiment_manifest(_root=None):
    """D224(b): HALT if any file hash in the experiment manifest has changed."""
    import hashlib
    _r = _root or ROOT
    m = json.loads(EXPERIMENT_MANIFEST.read_text())
    for path, expected in m["file_hashes"].items():
        p = _r / path
        if not p.exists():
            raise SystemExit(f"HALT: experiment manifest file missing: {path}")
        got = hashlib.sha256(p.read_bytes()).hexdigest()[:16]
        if got != expected:
            raise SystemExit(f"HALT: experiment manifest hash mismatch: {path} "
                             f"({got} != {expected}). This is a different experiment.")


def cross_week_check(board_root, season, week, reader_model, contracts):
    """D224(c): refuse a contract already frozen in ANY other week directory.

    contracts: list of (event_id, market_key, player_name, line) tuples.
    Returns list of (contract, week) for duplicates found.
    """
    dupes = []
    contract_set = set(contracts)
    for d in sorted(board_root.glob(f"week={season}_*/ai_opinions")):
        # Skip the current week
        dir_week = d.parent.name.split("_")[-1]
        if dir_week == f"{week:02d}":
            continue
        manifest_path = d / "manifest.json"
        if not manifest_path.exists():
            continue
        manifest = json.loads(manifest_path.read_text())
        for entry in manifest:
            rm = entry.get("reader_model", "legacy")
            if rm != reader_model or entry.get("pilot", False):
                continue
            f = d / entry["file"]
            if not f.exists():
                continue
            try:
                df = pd.read_parquet(f, columns=["event_id", "market_key", "player_name", "line"])
            except Exception:
                continue
            for _, r in df.iterrows():
                key = (r["event_id"], r["market_key"], r["player_name"], float(r["line"]))
                if key in contract_set:
                    dupes.append((key, d.parent.name))
    return dupes


# ── public helpers (tested directly) ──────────────────────────────────────────

def fill_sheet(sheet_df, picks_log, event_game_map=None):
    """D215(a)/D225: match picks_log to sheet and set p_first / tag / reason.

    Match key: (game_id, player_name, market_key derived from family, line).
    D225: game_id from the bundle's event_game_map prevents cross-event matches.
    If event_game_map is None, falls back to building game_id from sheet team names.
    picks_log.side: 'over' -> p_first = cal_p; 'under' -> p_first = 1 - cal_p
    (the sheet's first side is always Over for player props).
    More than one match for a key -> raises SystemExit (do not take the first).
    """
    from nfl.sim.names import FULL_TO_ABBR

    filled = sheet_df.copy()
    # D220: all no_view lines carry clip(book, 0.02, 0.98). The validator now accepts this.
    if "imp_first" in sheet_df.columns:
        book_p = np.where(filled["two_way"], filled["q_first"], filled["imp_first"])
    else:
        book_p = filled["q_first"].fillna(0.50)
    filled["p_first"] = np.clip(book_p, 0.02, 0.98)
    filled["tag"] = "no_view"
    filled["reason"] = ""

    # Build event_id -> game_id mapping
    if event_game_map is None:
        event_game_map = {}
        for _, r in filled.drop_duplicates("event_id").iterrows():
            h = FULL_TO_ABBR.get(r["home_team"], r["home_team"])
            a = FULL_TO_ABBR.get(r["away_team"], r["away_team"])
            event_game_map[r["event_id"]] = f"{a}@{h}"

    # Build a lookup from picks_log keyed by (game_id, player_name, market_key, line)
    pl_lookup = {}
    for _, r in picks_log.iterrows():
        mk = FAMILY_TO_MARKET.get(r["family"])
        if mk is None:
            continue
        gid = str(r.get("game_id", ""))
        key = (gid, r["player_name"], mk, float(r["line"]))
        if key in pl_lookup:
            raise SystemExit(f"HALT: duplicate picks_log key {key}")
        pl_lookup[key] = r

    n_matched = 0
    for idx, row in filled.iterrows():
        if not row.get("two_way", False):
            continue
        mk = str(row.get("market_key", ""))
        if mk in GAME_MARKETS:
            continue
        gid = event_game_map.get(row["event_id"], "")
        key = (gid, row["player_name"], mk, float(row["line"]))
        pl_row = pl_lookup.get(key)
        if pl_row is None:
            continue
        cal_p_over = float(pl_row["cal_p"])
        side = str(pl_row.get("side", "over"))
        if side == "under":
            p_first = 1.0 - cal_p_over
        else:
            p_first = cal_p_over
        p_first = float(np.clip(p_first, 0.02, 0.98))
        tier = str(pl_row.get("tier", ""))
        filled.at[idx, "p_first"] = round(p_first, 4)
        filled.at[idx, "tag"] = "sim_v1"
        filled.at[idx, "reason"] = f"sim v1 cal_p {tier}"[:160]
        n_matched += 1

    # Add conf and conf_rank (required by freeze)
    # conf = 100 * |p_first - book_p| for sim rows, 0 for no_view
    filled["conf"] = 0.0
    sim_mask = filled["tag"] == "sim_v1"
    if sim_mask.any():
        book_for_conf = filled.loc[sim_mask, "q_first"].fillna(
            filled.loc[sim_mask, "imp_first"] if "imp_first" in filled.columns else 0.50)
        filled.loc[sim_mask, "conf"] = (
            100 * abs(filled.loc[sim_mask, "p_first"] - book_for_conf)
        ).fillna(0).round(1).clip(0, 100)
    # conf_rank: 1-based rank by descending conf, ties broken by index
    filled["conf_rank"] = filled["conf"].rank(method="first", ascending=False).astype(int)

    # D220: sim_v1 rows == matched two-way prop rows exactly
    n_sim_v1 = (filled["tag"] == "sim_v1").sum()
    assert n_sim_v1 == n_matched, (
        f"sim_v1 count {n_sim_v1} != matched {n_matched}")

    return filled, n_matched


def anchor_sidecar(anchoring_log_df, lines):
    """D215(b)/D226: per-game anchor sidecar from the anchoring log.

    Best iteration = min |err_m| + |err_t| (same rule as run_week).
    Market spread/total MUST come from the actual lines dict used by the sim
    (D226: not reconstructed from err fields; CAR@ATL -3.0/43.5 came out
    -3.2572/43.9996 when using the fallback). The lines dict is keyed by
    game_id (away@home) with keys 'spread' and 'total'.
    """
    required = {"game", "iter", "margin", "total", "err_m", "err_t", "converged"}
    missing = required - set(anchoring_log_df.columns)
    if missing:
        raise KeyError(f"anchoring_log missing columns: {missing}")

    rows = []
    for gname in anchoring_log_df["game"].unique():
        g = anchoring_log_df[anchoring_log_df["game"] == gname]
        best = g.loc[(abs(g["err_m"]) + abs(g["err_t"])).idxmin()]
        anch_m = float(best["margin"])
        anch_t = float(best["total"])
        # D226: actual market targets from lines — never reconstructed
        ln = lines.get(gname)
        if ln is None:
            raise SystemExit(
                f"HALT: no lines entry for {gname} — anchor sidecar requires "
                f"actual market targets, not reconstructed values")
        spread = float(ln["spread"])
        total_line = float(ln["total"])
        miss_m = abs(anch_m - spread)
        miss_t = abs(anch_t - total_line)
        rows.append({
            "game": gname,
            "target_spread": spread, "target_total": total_line,
            "anch_m": round(anch_m, 4), "anch_t": round(anch_t, 4),
            "miss_m": round(miss_m, 4), "miss_t": round(miss_t, 4),
            "iterations": int(best["iter"]) + 1,
            "converged": bool(best["converged"]),
            "anchored": miss_m <= ANCHOR_MISS_TOL and miss_t <= ANCHOR_MISS_TOL,
        })
    return pd.DataFrame(rows)


# ── main ──────────────────────────────────────────────────────────────────────

def _default_run_week(root, week, T, bundle_lines, game_ids):
    """Default run_week_fn: call run_week.py via subprocess with --lines-json and --games."""
    lines_json = json.dumps(bundle_lines)
    games_str = ",".join(game_ids)
    cmd = [sys.executable, str(root / "nfl" / "sim" / "run_week.py"),
           "--week", str(week), "--as-of", T.isoformat(),
           "--lines-json", lines_json, "--games", games_str]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(root), timeout=7200)
    if r.returncode != 0:
        raise SystemExit(f"HALT: run_week.py failed:\n{r.stderr}\n{r.stdout}")
    print(f"    Sim complete.\n{r.stdout[-500:]}\n", flush=True)


def main(argv=None, root=None, run_week_fn=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--as-of", help="UTC ISO timestamp (pilot only)")
    ap.add_argument("--window-hours", type=float, help="limit to games kicking within N hours")
    ap.add_argument("--events", help="comma-separated team fragments")
    ap.add_argument("--dry-run", action="store_true", help="D221: steps a-d and f, stop before freeze")
    ap.add_argument("--allow-stale-quotes", action="store_true",
                    help="pilot only: override the quote-age HALT")
    a = ap.parse_args(argv)

    root = Path(root) if root else ROOT
    if run_week_fn is None:
        run_week_fn = _default_run_week

    # D229: override module-level paths when root is provided
    global PROPS_DIR, LINES_DIR, BOARD_ROOT, EXPERIMENT_MANIFEST
    PROPS_DIR = root / "data" / "odds_archive" / "nfl" / "props"
    LINES_DIR = root / "data" / "odds_archive" / "nfl" / "line_history"
    BOARD_ROOT = root / "nfl" / "data" / "board"
    EXPERIMENT_MANIFEST = root / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json"

    if a.as_of and not a.pilot:
        raise SystemExit("HALT: --as-of requires --pilot")
    if a.allow_stale_quotes and not a.pilot:
        raise SystemExit("HALT: --allow-stale-quotes requires --pilot")

    T = datetime.fromisoformat(a.as_of) if a.as_of else datetime.now(timezone.utc)
    if T.tzinfo is None:
        T = T.replace(tzinfo=timezone.utc)

    # (a) test_freeze_v1 + experiment manifest check
    print("(a) Running test_freeze_v1...", flush=True)
    import pytest
    test_args = ["-q", "-p", "no:cacheprovider",
                 str(ROOT / "nfl" / "sim" / "tests" / "test_freeze_v1.py")]
    ret = pytest.main(test_args, plugins=[])
    if ret != 0:
        raise SystemExit(f"HALT: test_freeze_v1 failed (exit {ret})")
    print("    PASS", flush=True)
    check_experiment_manifest(_root=root)
    print("    Experiment manifest: OK", flush=True)
    from nfl.sim.run_week import _check_calibration_stamp
    from nfl.sim.calibration import usage_fingerprint
    stamp_ok, stamp_mismatches = _check_calibration_stamp()
    if not stamp_ok:
        raise SystemExit("HALT: calibration stamp mismatch:\n" +
                 "\n".join(f"  {m}" for m in stamp_mismatches))
    print("    Calibration stamp: OK", flush=True)
    em = json.loads(EXPERIMENT_MANIFEST.read_text())
    live_usage = usage_fingerprint()
    if live_usage != em.get("usage_fingerprint"):
        raise SystemExit(f"HALT: usage fingerprint mismatch: live={live_usage}, "
                 f"manifest={em.get('usage_fingerprint')}")
    print("    Usage fingerprint: OK\n", flush=True)

    # (b) D225: build immutable run bundle at cutoff T
    print(f"(b) Building bundle at T={T.isoformat()}...", flush=True)
    bundle_dir, bundle_manifest = build_bundle(
        SEASON, a.week, T, pilot=a.pilot,
        allow_stale_quotes=a.allow_stale_quotes,
        window_hours=a.window_hours, event_filter=a.events, _root=root)
    print(flush=True)

    events_df = pd.read_parquet(bundle_dir / "events.parquet")
    event_game_map = dict(zip(events_df["event_id"], events_df["game_id"]))

    # D229: freshness HALTs (not warns)
    freshness = json.loads((bundle_dir / "freshness.json").read_text())
    for label in ("team_ratings", "tendencies", "usage"):
        mw = freshness.get(f"{label}_max_week")
        if mw is None or mw < a.week - 1:
            raise SystemExit(
                f"HALT: {label} max week = {mw} (need >= {a.week - 1} for season {SEASON})")
    kickers = freshness.get("kickers", "missing")
    if kickers == "engine_default_fallback":
        print(f"  kickers: fallback (no {SEASON} rows) — declared, recorded in bundle",
              flush=True)

    # (c) D229: build sheet IN-PROCESS from the bundle's props and lines
    print("(c) Building sheet from bundle...", flush=True)
    from nfl.pipeline.log_ai_opinions import build_sheet, set_sport
    set_sport("nfl")
    bundle_props = pd.read_parquet(bundle_dir / "props.parquet")
    bundle_lines_df = pd.read_parquet(bundle_dir / "lines.parquet")
    sheet_df = build_sheet(bundle_props, bundle_lines_df, T)
    # Restrict to the bundle's event_ids
    bundle_eids = set(events_df["event_id"])
    sheet_df = sheet_df[sheet_df["event_id"].isin(bundle_eids)].reset_index(drop=True)
    n_two_way = int(sheet_df["two_way"].sum()) if "two_way" in sheet_df.columns else 0
    print(f"    {len(sheet_df)} lines, {n_two_way} two-way\n", flush=True)

    # (d) sim — only the bundle's events
    print("(d) Running sim...", flush=True)
    bundle_lines = lines_dict_from_bundle(bundle_dir)
    game_ids = sorted(bundle_lines.keys())
    sim_out = root / "nfl" / "data" / "sim" / "outputs" / f"week={SEASON}_{a.week:02d}"
    run_week_fn(root, a.week, T, bundle_lines, game_ids)

    # Read picks_log
    picks_log = pd.read_parquet(sim_out / "picks_log.parquet")
    print(f"    picks_log: {len(picks_log)} legs", flush=True)

    # (e) fill
    print("(e) Filling opinions...", flush=True)
    filled, n_matched = fill_sheet(sheet_df, picks_log, event_game_map=event_game_map)
    print(f"    Matched {n_matched} / {n_two_way} two-way prop rows\n", flush=True)

    # D229: validate filled prices against bundle's sheet
    for col in ("price_first", "price_second", "source_utc"):
        if col in sheet_df.columns and col in filled.columns:
            sheet_vals = sheet_df.set_index(["event_id", "market_key", "player_name", "line"])[col]
            filled_vals = filled.set_index(["event_id", "market_key", "player_name", "line"])[col]
            joined = sheet_vals.align(filled_vals, join="inner")
            mismatches = joined[0] != joined[1]
            if mismatches.any():
                n_bad = int(mismatches.sum())
                raise SystemExit(
                    f"HALT: {n_bad} {col} mismatch(es) between sheet and filled — "
                    f"bundle prices must be used verbatim")

    sim_rows = filled[filled["tag"] == "sim_v1"]
    print(f"    Coverage: {len(sheet_df)} sheet / {n_two_way} two-way / "
          f"{n_matched} matched", flush=True)
    if len(sim_rows) and "market_key" in sim_rows.columns:
        print("    By market:")
        print(sim_rows.groupby("market_key").size().to_string(header=False))

    if n_matched == 0:
        raise SystemExit("HALT: zero sim matches — nothing to freeze")

    # (f) anchor sidecar
    print("(f) Building anchor sidecar...", flush=True)
    anch_log_path = sim_out / "anchoring_log.parquet"
    if not anch_log_path.exists():
        raise SystemExit("HALT: anchoring_log.parquet missing — sidecar is mandatory (D226)")
    anch_log = pd.read_parquet(anch_log_path)
    sidecar_df = anchor_sidecar(anch_log, bundle_lines)
    sidecar_path = bundle_dir / "anchor_sidecar.parquet"
    sidecar_df.to_parquet(sidecar_path, index=False)
    n_unanch = int((~sidecar_df["anchored"]).sum())
    print(f"    {len(sidecar_df)} games, {n_unanch} unanchored", flush=True)
    print(sidecar_df.to_string(index=False))

    # dry-run
    if a.dry_run:
        print("\n--- DRY RUN ---")
        print(f"Tag counts:\n{filled['tag'].value_counts().to_string()}")
        print(f"\nBundle manifest: {bundle_dir.relative_to(root)}/bundle_manifest.json")
        print(json.dumps(bundle_manifest, indent=1))
        print("\nDRY RUN complete — nothing frozen.")
        return

    # (g) D229: freeze IN-PROCESS
    freeze_wall = datetime.now(timezone.utc)
    first_kick = events_df["commence_time"].map(_parse_utc).min()
    if freeze_wall >= first_kick:
        raise SystemExit(f"HALT: publication time {freeze_wall.isoformat()} >= "
                     f"first kick {first_kick.isoformat()}")

    print("(g) Freezing...", flush=True)
    from nfl.pipeline.log_ai_opinions import freeze as do_freeze
    board_root = root / "nfl" / "data" / "board"
    opinions_dir = board_root / f"week={SEASON}_{a.week:02d}" / "ai_opinions"
    dest, sha, m = do_freeze(
        sheet_df, filled, SEASON, a.week, a.pilot, T,
        d=opinions_dir, reader_model=READER_MODEL, board_root=board_root)
    print(f"    FROZEN {len(m)} lines -> {dest.relative_to(root)}\n"
          f"    sha256 {sha}\n", flush=True)

    # Write sidecar to opinions dir
    sidecar_df.to_parquet(
        opinions_dir / "anchor_sidecar_sim_v1.parquet", index=False)

    # Record publication time in the bundle
    bundle_manifest["publication_utc"] = freeze_wall.isoformat()
    bundle_manifest["cutoff_T"] = T.isoformat()
    (bundle_dir / "bundle_manifest.json").write_text(
        json.dumps(bundle_manifest, indent=1) + "\n")

    print("\nDone.")
    return dest


if __name__ == "__main__":
    main()
