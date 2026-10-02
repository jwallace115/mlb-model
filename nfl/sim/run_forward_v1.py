#!/usr/bin/env python3
"""
FWD1 (D211/D215): forward-test harness for the frozen NFL sim v1.

Usage:
  python3 nfl/sim/run_forward_v1.py --week 3 [--pilot] [--as-of ...] [--window-hours 9] [--events pit,cle]
"""

import argparse, hashlib, json, os, shutil, subprocess, sys, time
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
RECEIPTS_REL = Path("research") / "nfl_sim" / "fwd_v1_receipts.jsonl"

# D256: files copied into <run-dir>/inputs. The first group is read by the prediction
# (read_set.REQUIRED_INPUTS); depth charts and injuries are kept as record only.
RATINGS_FILES = [
    "team_ratings_weekly.parquet", "tendencies_weekly.parquet",
    "tendencies_situational_weekly.parquet", "qb_ratings_weekly.parquet",
    "kicker_weekly.parquet", "league_baselines.parquet",
    "player_usage_weekly.parquet", "active_universe_weekly.parquet",
]
PBP_DIR_FILES = ["rosters_weekly.parquet", "injuries.parquet"]   # D271: injuries required
RECORD_ONLY_FILES = ["depth_charts.parquet"]


def archive_root_for(repo_root):
    """D256(d): content-addressed archive OUTSIDE git, beside the repo
    (~/mlb-model -> ~/mlb-model-archive/nfl_fwd_v1). NFL_FWD_ARCHIVE overrides."""
    env = os.environ.get("NFL_FWD_ARCHIVE")
    return Path(env) if env else Path(repo_root).resolve().parent / "mlb-model-archive" / "nfl_fwd_v1"


def archive_file(fpath, archive_root):
    """Copy fpath into archive_root/sha256/<hash> (once) and verify the stored copy."""
    data = Path(fpath).read_bytes()
    h = hashlib.sha256(data).hexdigest()
    dest = Path(archive_root) / "sha256" / h
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".tmp")
        tmp.write_bytes(data)
        tmp.rename(dest)
    if hashlib.sha256(dest.read_bytes()).hexdigest() != h:
        raise SystemExit(f"HALT: archive copy of {fpath} is corrupt ({dest})")
    return h


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
        # D257(a): a snapshot is usable only if EVERY row existed at T (not just its first row)
        row_ts = df["snapshot_utc"].map(_parse_utc)
        if row_ts.max() <= T:
            candidates.append((row_ts.max(), s, df))
    if not candidates:
        raise SystemExit("HALT: no game-line snapshot ≤ T")
    # Take the newest snapshot ≤ T
    candidates.sort(key=lambda x: x[0])
    _, spath, lines = candidates[-1]
    if lines["snapshot_utc"].map(_parse_utc).nunique() > 1:
        raise SystemExit(f"HALT: inconsistent game-line snapshot {spath.name}: "
                         f"rows carry more than one snapshot_utc")
    return lines[lines["bookmaker"] == BOOK].copy()


def _last_played_weeks(pbp_path, week):
    """D256(c): each team's last COMPLETED game week before `week`, from the PBP file.
    A game counts as completed when it has an END GAME row. HALTs if the PBP file has no
    completed game in week-1 (the PBP is stale, so 'last played' cannot be trusted)."""
    from nfl.sim.names import FULL_TO_ABBR  # noqa: F401 (PBP already uses abbreviations)
    cols = ["game_id", "week", "home_team", "away_team", "desc"]
    pbp = pd.read_parquet(pbp_path, columns=cols)
    pbp = pbp[pbp["week"] < week]
    done = pbp.groupby("game_id")["desc"].apply(
        lambda d: d.astype(str).str.contains("END GAME", case=False).any())
    games = pbp.drop_duplicates("game_id").set_index("game_id")
    games = games[done.reindex(games.index).fillna(False).astype(bool)]
    if week > 1 and not (games["week"] == week - 1).any():
        raise SystemExit(f"HALT: {Path(pbp_path).name} has no completed week-{week - 1} game; "
                         f"per-team freshness cannot be established")
    last = {}
    for _, g in games.iterrows():
        for t in (g["home_team"], g["away_team"]):
            last[t] = max(last.get(t, 0), int(g["week"]))
    return last


REQUIRED_RATING_UNITS = ("pass_off", "pass_def", "rush_off", "rush_def")


def _team_freshness(inputs_dir, season, week, teams, last_week):
    """D256(c), amended D271: per participating team, on the consumed copies.

    Every ratings table is "entering week w" (built from games in weeks < w), and the
    engine selects row W, else the latest row <= W. So the row selected for a team must be
    >= (its last played week + 1): built from its most recent game. D271 found the old
    rule (">= last played week") passing a week-4 run on usage built from week-1 games.
    - every table: selected week >= last played week + 1;
    - the active universe for week W must be the one built from THIS week's rosters and
      injury report (bundle copies): same skill players, same active flags. A row copied
      forward from an earlier week, or one built before an injury report, fails;
    - a team's last played week must be >= week-2 (no team is idle two weeks running).
    Returns the table; HALTs on any failure."""
    per_game = {"team_ratings": "team_ratings_weekly.parquet",
                "tendencies": "tendencies_weekly.parquet",
                "tendencies_situational": "tendencies_situational_weekly.parquet"}
    per_played = {"usage": "player_usage_weekly.parquet",
                  "active_universe": "active_universe_weekly.parquet",
                  "kickers": "kicker_weekly.parquet",
                  "qb_ratings": "qb_ratings_weekly.parquet"}
    # D260: measure the row the engine's selector will actually use — the latest week
    # <= the target week (engine._get_team_rating & co: week == W, else max week <= W) —
    # not an unrestricted maximum. Team ratings are selected per unit, so a team's value
    # is its WORST unit.
    maxw = {}
    for label, fname in {**per_game, **per_played}.items():
        cols = ["season", "week", "team"] + (["unit"] if label == "team_ratings" else [])
        df = pd.read_parquet(inputs_dir / fname, columns=cols)
        df = df[(df["season"] == season) & (df["week"] <= week)]
        if label == "team_ratings":
            # D263 (audit #10 A5): each REQUIRED unit by name; an unknown label never
            # substitutes for a required one, and extra labels are ignored.
            per_unit = df.groupby(["team", "unit"])["week"].max()
            sel = {}
            for t in df["team"].unique():
                ws = [per_unit.get((t, u)) for u in REQUIRED_RATING_UNITS]
                sel[t] = -1 if any(w is None for w in ws) else int(min(ws))
            maxw[label] = sel
        else:
            maxw[label] = df.groupby("team")["week"].max().to_dict()
    table, bad = {}, []
    for t in teams:
        lp = last_week.get(t)
        row = {"last_played_week": lp}
        if week > 1 and (lp is None or lp < week - 2):
            bad.append(f"{t}: last played week {lp} (< {week - 2})")
        for label in per_game:
            w = maxw[label].get(t)
            row[label] = None if w is None else int(w)
            if w is None or w < week - 1:
                bad.append(f"{t}: {label} max week {w} (need >= {week - 1})")
        for label in per_played:
            w = maxw[label].get(t)
            row[label] = None if w is None else int(w)
        # D271: every table must include the team's most recent game
        if week > 1:
            for label in list(per_game) + list(per_played):
                w = row.get(label)
                if w is None or lp is None or w < lp + 1:
                    bad.append(f"{t}: {label} selected week {w} — built without its last "
                               f"game (need >= last played {lp} + 1)")
        row["active_universe_current"] = _active_universe_matches(inputs_dir, season, week, t, bad)
        # recorded, not gated (about 2% of team-weeks list no game status at all): how many
        # game statuses this week's injury report carries — 0 before the final report
        inj = pd.read_parquet(inputs_dir / "injuries.parquet", columns=["season", "week", "team",
                                                                         "report_status"])
        row["injury_game_statuses"] = int(inj[(inj["season"] == season) & (inj["week"] == week)
                                              & (inj["team"] == t)]["report_status"].notna().sum())
        table[t] = row
    if bad:
        raise SystemExit("HALT: per-team input freshness failed:\n" +
                         "\n".join(f"  {b}" for b in bad))
    return table


AU_SKILL_POS = {"RB", "WR", "TE", "QB"}          # usage.SKILL_POS


def _active_universe_matches(inputs_dir, season, week, team, bad):
    """D271: the week-W active universe of `team` must equal what usage.build_active_universe
    derives from the bundle's week-W rosters and injury report: active = roster status ACT
    and injury report status not Out/Doubtful. Returns the number of active players."""
    ros = pd.read_parquet(inputs_dir / "rosters_weekly.parquet",
                          columns=["season", "week", "team", "gsis_id", "position", "status"])
    ros = ros[(ros["season"] == season) & (ros["week"] == week) & (ros["team"] == team)
              & ros["position"].isin(AU_SKILL_POS)]
    if ros.empty:
        bad.append(f"{team}: no week-{week} rosters in the bundle — the active universe "
                   f"cannot be current")
        return None
    inj = pd.read_parquet(inputs_dir / "injuries.parquet",
                          columns=["season", "week", "team", "gsis_id", "report_status"])
    inj = inj[(inj["season"] == season) & (inj["week"] == week) & (inj["team"] == team)]
    if inj.empty:
        bad.append(f"{team}: no week-{week} injury report in the bundle")
        return None
    # same row resolution as build_active_universe: a left merge keeps the FIRST injury
    # row per player, and drop_duplicates keeps the FIRST roster row per player
    inj = inj.drop_duplicates("gsis_id", keep="first")
    ros = ros.drop_duplicates("gsis_id", keep="first")
    out = set(inj.loc[inj["report_status"].isin(["Out", "Doubtful"]), "gsis_id"])
    want = {pid: bool(st == "ACT" and pid not in out)
            for pid, st in zip(ros["gsis_id"], ros["status"])}
    au = pd.read_parquet(inputs_dir / "active_universe_weekly.parquet",
                         columns=["season", "week", "team", "player_id", "active_flag"])
    au = au[(au["season"] == season) & (au["week"] == week) & (au["team"] == team)]
    have = {pid: bool(f) for pid, f in zip(au["player_id"], au["active_flag"])}
    if have != want:
        diff = sorted(set(want) ^ set(have)) + sorted(
            p for p in set(want) & set(have) if want[p] != have[p])
        bad.append(f"{team}: week-{week} active universe was not built from this week's "
                   f"rosters and injury report ({len(diff)} players differ, e.g. {diff[:5]})")
        return None
    return sum(want.values())


SCHEDULE_COLS = ["game_id", "season", "game_type", "week", "gameday", "gametime",
                 "home_team", "away_team"]


def _load_schedule(season, root):
    """D261: the nflverse schedule for the season — a local snapshot
    (nfl/data/pbp/schedules_<season>.parquet) when present, otherwise nflreadpy. It is
    copied into the run directory, hashed and archived."""
    local = Path(root) / "nfl" / "data" / "pbp" / f"schedules_{season}.parquet"
    if local.exists():
        df, src = pd.read_parquet(local), f"local {local.name}"
    else:
        try:
            import nflreadpy
            df, src = nflreadpy.load_schedules([season]).to_pandas(), "nflreadpy"
        except Exception as e:
            raise SystemExit(f"HALT: no schedule for {season} (no {local.name}, nflreadpy "
                             f"failed: {e}) — the event mapping is required at freeze time")
    missing = [c for c in SCHEDULE_COLS if c not in df.columns]
    if missing:
        raise SystemExit(f"HALT: schedule is missing columns {missing}")
    df = df[df["season"] == season][SCHEDULE_COLS].reset_index(drop=True)
    return df, src


def _map_events_to_schedule(events, sched, week):
    """D261 (S2): each event must match EXACTLY ONE schedule game of this week with the
    same home and away team, kicking within 60 min of the event's commence_time (nflverse
    gameday/gametime are US Eastern). Returns the nflverse game_id per event."""
    from zoneinfo import ZoneInfo
    et = ZoneInfo("America/New_York")
    out, bad = [], []
    for _, ev in events.iterrows():
        c = sched[(sched["week"] == week) & (sched["home_team"] == ev["home_abbr"]) &
                  (sched["away_team"] == ev["away_abbr"])]
        if len(c) != 1:
            bad.append(f"{ev['game_id']}: {len(c)} schedule matches in week {week}")
            out.append(None)
            continue
        r = c.iloc[0]
        kick = datetime.strptime(f"{r['gameday']} {r['gametime']}", "%Y-%m-%d %H:%M") \
            .replace(tzinfo=et).astimezone(timezone.utc)
        if abs((kick - _parse_utc(ev["commence_time"])).total_seconds()) > 3600:
            bad.append(f"{ev['game_id']}: schedule kick {kick.isoformat()} vs event "
                       f"{ev['commence_time']}")
        out.append(r["game_id"])
    if bad:
        raise SystemExit("HALT: events do not map to the schedule:\n" +
                         "\n".join(f"  {b}" for b in bad))
    return out


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
    # D241(a): REFUSE an existing run directory — no exist_ok
    if bundle_dir.exists():
        raise SystemExit(f"HALT: run directory already exists: {bundle_dir}\n"
                         f"A run_id can only be used once.")
    bundle_dir.mkdir(parents=True, exist_ok=False)

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

    # ── D257(a): per-row quote checks (props AND lines) ──
    # Every consumed row must have existed at T and be at most QUOTE_MAX_AGE_H old —
    # judged on each row's own timestamp, never on a first row per event or file.
    def _ages_h(df, col):
        ts = df[col].map(_parse_utc)
        return ts, ts.map(lambda t: (T - t).total_seconds() / 3600)

    for df, col, label in [(props, "pull_timestamp", "props pull"),
                           (lines, "snapshot_utc", "game-line snapshot")]:
        if df.empty:
            continue
        if col not in df.columns:
            raise SystemExit(f"HALT: {label} rows have no {col}")
        ts, age = _ages_h(df, col)
        if (ts > T).any():
            raise SystemExit(f"HALT: {int((ts > T).sum())} {label} row(s) timestamped after "
                             f"T={T.isoformat()} (latest {ts.max().isoformat()})")
        if age.max() > QUOTE_MAX_AGE_H and not allow_stale_quotes:
            worst = df.loc[age.idxmax(), "event_id"]
            raise SystemExit(
                f"HALT: {label} is {age.max():.1f}h old for event {worst} "
                f"(max allowed: {QUOTE_MAX_AGE_H}h). "
                f"Use --allow-stale-quotes with --pilot or --dry-run.")

    # D257(a): every event's rows agree on teams and kickoff across props and lines
    meta = pd.concat([d[["event_id", "home_team", "away_team", "commence_time"]]
                      for d in (props, lines) if not d.empty], ignore_index=True)
    meta["commence_time"] = meta["commence_time"].map(lambda c: _parse_utc(c).isoformat())
    inconsistent = meta.drop_duplicates().groupby("event_id").size()
    inconsistent = inconsistent[inconsistent > 1]
    if len(inconsistent):
        raise SystemExit(f"HALT: inconsistent teams/kickoff within event(s) "
                         f"{list(inconsistent.index)[:5]} across props and lines")
    if events["game_id"].duplicated().any():
        raise SystemExit("HALT: two events map to the same game_id in the window")

    _r = _root or ROOT

    # D261 (S2): freeze the event -> nflverse game_id mapping, with the schedule snapshot
    sched, sched_src = _load_schedule(season, _r)
    events = events.copy()
    events["nflverse_game_id"] = _map_events_to_schedule(events, sched, week)

    # ── write ──
    events.to_parquet(bundle_dir / "events.parquet", index=False)
    props.to_parquet(bundle_dir / "props.parquet", index=False)
    lines.to_parquet(bundle_dir / "lines.parquet", index=False)

    # D241(b)/D256: copy every prediction input into the run directory; the prediction
    # reads ONLY these copies (run_week --input-dir; proven by the read set).
    inputs_dir = bundle_dir / "inputs"
    inputs_dir.mkdir()
    sched.to_parquet(inputs_dir / "schedule.parquet", index=False)
    ratings_dir = _r / "nfl" / "data" / "sim" / "ratings"
    pbp_dir = _r / "nfl" / "data" / "pbp"
    for src_dir, names, required in [(ratings_dir, RATINGS_FILES, True),
                                     (pbp_dir, PBP_DIR_FILES, True),
                                     (pbp_dir, RECORD_ONLY_FILES, False)]:
        for fname in names:
            src = src_dir / fname
            if src.exists():
                shutil.copy2(src, inputs_dir / fname)
            elif required:
                raise SystemExit(f"HALT: prediction input missing: {src}")

    # D256(a): completed-game counts (the board's stale flag) and each team's last played
    # week, computed ONCE here from the shared PBP and frozen into the run directory.
    pbp_path = pbp_dir / f"pbp_{season}.parquet"
    if not pbp_path.exists():
        raise SystemExit(f"HALT: {pbp_path} missing — needed for per-team freshness")
    from nfl.sim.run_week import count_team_completed_games
    # D263 (audit #10 A3): read the shared PBP ONCE into the content-addressed archive and
    # derive the counts, the last-played weeks and the recorded hash all from that one
    # immutable snapshot (a refresh of the shared file mid-build can no longer mix versions).
    pbp_sha = archive_file(pbp_path, archive_root_for(_r))
    pbp_snap = archive_root_for(_r) / "sha256" / pbp_sha
    counts = count_team_completed_games(season, pbp_path=pbp_snap)
    last_week = _last_played_weeks(pbp_snap, week)
    if hashlib.sha256(pbp_snap.read_bytes()).hexdigest() != pbp_sha:
        raise SystemExit("HALT: the archived PBP snapshot changed while it was being read")
    (inputs_dir / "team_game_counts.json").write_text(
        json.dumps({"counts": counts, "last_played_week": last_week,
                    "source": pbp_path.name, "source_sha256": pbp_sha},
                   indent=1, sort_keys=True) + "\n")

    # D256(c): freshness judged on the CONSUMED copies, for each participating team
    teams = sorted(set(events["home_abbr"]) | set(events["away_abbr"]))
    freshness = {"cutoff_T": T.isoformat(), "run_id": run_id, "schedule_source": sched_src,
                 "per_team": _team_freshness(inputs_dir, season, week, teams, last_week)}
    (bundle_dir / "freshness.json").write_text(json.dumps(freshness, indent=1) + "\n")

    # ── sha256 manifest — hashes EVERY file in the run directory ──
    manifest = {}
    for fpath in sorted(bundle_dir.rglob("*")):
        if fpath.is_file() and fpath.name != "bundle_manifest.json":
            rel = str(fpath.relative_to(bundle_dir))
            manifest[rel] = hashlib.sha256(fpath.read_bytes()).hexdigest()
    manifest["pilot"] = pilot
    manifest["allow_stale_quotes"] = allow_stale_quotes
    (bundle_dir / "bundle_manifest.json").write_text(json.dumps(manifest, indent=1) + "\n")
    # D256(d): archive every file now, so the inputs survive even if the run stops later
    arch = archive_root_for(_r)
    for fpath in sorted(bundle_dir.rglob("*")):
        if fpath.is_file():
            archive_file(fpath, arch)

    print(f"  Bundle: {bundle_dir.relative_to(_r)}")
    print(f"  Events: {len(events)}, Props: {len(props)}, Lines: {len(lines)}")
    print(f"  Archive: {arch}")
    print("  Per-team freshness (consumed copies):")
    for t, row in freshness["per_team"].items():
        print(f"    {t}: " + ", ".join(f"{k}={v}" for k, v in row.items()))

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


def _finalize_bundle_manifest(bundle_dir):
    """D241(f)/D260: add the run's new files (outputs, sidecar) to the manifest.

    The build-time manifest is the record of what the prediction consumed: every file it
    lists must still have exactly its build-time hash, or this HALTs. Finalisation only
    ADDS hashes; it never re-authorises a changed input."""
    old = bundle_dir / "bundle_manifest.json"
    prev = json.loads(old.read_text())
    manifest = dict(prev)
    changed = []
    for fpath in sorted(bundle_dir.rglob("*")):
        if not fpath.is_file() or fpath.name in ("bundle_manifest.json", "publication.json"):
            continue
        rel = str(fpath.relative_to(bundle_dir))
        h = hashlib.sha256(fpath.read_bytes()).hexdigest()
        if rel in prev and isinstance(prev[rel], str) and len(prev[rel]) == 64:
            if prev[rel] != h:
                changed.append(rel)
        else:
            manifest[rel] = h
    missing = [k for k, v in prev.items() if isinstance(v, str) and len(v) == 64
               and not (bundle_dir / k).exists()]
    if changed or missing:
        raise SystemExit("HALT: run-directory files changed or vanished after the bundle was "
                         f"built: changed={changed} missing={missing}")
    old.write_text(json.dumps(manifest, indent=1) + "\n")
    # D256(d): every run-directory file also goes to the content-addressed archive
    arch = archive_root_for(bundle_dir.parents[5])
    for fpath in sorted(bundle_dir.rglob("*")):
        if fpath.is_file():
            archive_file(fpath, arch)


def append_receipt(root, receipt):
    """D258(b): append one publication receipt (one JSON line) to the registry."""
    path = Path(root) / RECEIPTS_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as fh:
        fh.write(json.dumps(receipt, sort_keys=True) + "\n")


def archive_receipt(archive_root, receipt):
    """D260: one immutable receipt per run in <archive>/receipts/<run_id>.json."""
    d = Path(archive_root) / "receipts"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{receipt['run_id']}.json"
    body = json.dumps(receipt, indent=1, sort_keys=True) + "\n"
    if f.exists() and f.read_text() != body:
        raise SystemExit(f"HALT: a different receipt for run {receipt['run_id']} is already archived")
    f.write_text(body)


def load_receipts(root):
    path = Path(root) / RECEIPTS_REL
    if not path.exists():
        return []
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


RUNTIME_KEYS = ("runtime", "runtime_before_freeze", "runtime_worker")


def dependency_drift(baseline_runtimes, runtimes):
    """D270 (audit #13 A1): the pre-registered dependency rule, as one predicate.

    The baseline is the UNION of dependency_distributions over the first primary
    receipt's three runtimes (which must agree with each other on every shared name),
    plus their (python, executable). A later run's runtimes are consistent only if every
    distribution ANY of them loaded is in the baseline with the same version, location and
    RECORD sha256, and each ran the baseline's python and executable. A distribution that
    is not in the baseline at all is drift. Returns the list of violations ([] = none)."""
    problems, base, interp = [], {}, set()
    for rt in baseline_runtimes:
        if not rt:
            problems.append("baseline: a runtime is missing")
            continue
        interp.add((rt.get("python"), rt.get("executable")))
        for name, ident in (rt.get("dependency_distributions") or {}).items():
            if name in base and base[name] != ident:
                problems.append(f"baseline: {name} differs between its own runtimes")
            base.setdefault(name, ident)
    if len(interp) != 1:
        problems.append(f"baseline: {len(interp)} interpreters")
    for label, rt in runtimes.items():
        if not rt:
            problems.append(f"{label}: no verified runtime")
            continue
        if (rt.get("python"), rt.get("executable")) not in interp:
            problems.append(f"{label}: interpreter {rt.get('python')} {rt.get('executable')} "
                            f"is not the baseline's")
        for name, ident in sorted((rt.get("dependency_distributions") or {}).items()):
            if name not in base:
                problems.append(f"{label}: {name} {ident.get('version')} is not in the baseline")
            elif base[name] != ident:
                problems.append(f"{label}: {name} differs from the baseline")
    return problems


def receipt_status(run_id, root):
    """D258(b): 'complete' | 'no receipt' | 'mismatch' for one run_id."""
    root = Path(root)
    recs = [r for r in load_receipts(root) if r.get("run_id") == run_id]
    if not recs:
        return "no receipt"
    if len(recs) > 1:
        return "mismatch"
    r = recs[0]
    runs = list((root / "nfl" / "data" / "board").glob(f"week=*/sim_runs/{run_id}"))
    if len(runs) != 1:
        return "mismatch"
    pub = runs[0] / "publication.json"
    frozen = root / r["frozen_file"]
    if not pub.exists() or hashlib.sha256(pub.read_bytes()).hexdigest() != r["publication_json_sha256"]:
        return "mismatch"
    if not frozen.exists() or hashlib.sha256(frozen.read_bytes()).hexdigest() != r["frozen_sha256"]:
        return "mismatch"
    if hashlib.sha256((runs[0] / "bundle_manifest.json").read_bytes()).hexdigest() != r["bundle_digest"]:
        return "mismatch"
    # D266 (audit #11 B): the ai_opinions manifest entry must be the receipt's, exactly
    entry = r.get("opinions_manifest_entry")
    if entry is not None:
        om = frozen.parent / "manifest.json"
        entries = json.loads(om.read_text()) if om.exists() else []
        if [e for e in entries if e.get("file") == entry.get("file")] != [entry]:
            return "mismatch"
    return "complete"


def verify_bundle(bundle_dir):
    """D241(f): verify every file in the run directory against the manifest.
    D258(b): a file not in the manifest (other than publication.json) is a mismatch, and
    when a receipt names this run, publication.json must exist with the receipt's hash.
    Returns list of mismatches (empty = OK)."""
    # Metadata keys that are NOT file hashes
    META_KEYS = {"pilot", "allow_stale_quotes", "publication_utc", "cutoff_T",
                 "experiment_digest", "bundle_digest"}
    man_path = bundle_dir / "bundle_manifest.json"
    if not man_path.exists():
        return ["bundle_manifest.json missing"]
    manifest = json.loads(man_path.read_text())
    bad = []
    for rel, expected in manifest.items():
        if rel in META_KEYS:
            continue
        if not isinstance(expected, str) or len(expected) < 32:
            continue  # metadata key, not a hash
        fpath = bundle_dir / rel
        if not fpath.exists():
            bad.append(f"missing: {rel}")
            continue
        got = hashlib.sha256(fpath.read_bytes()).hexdigest()
        if got != expected:
            bad.append(f"hash mismatch: {rel} ({got[:16]} != {expected[:16]})")
    listed = {k for k, v in manifest.items() if isinstance(v, str) and len(v) >= 32}
    for fpath in sorted(bundle_dir.rglob("*")):
        if fpath.is_file():
            rel = str(fpath.relative_to(bundle_dir))
            if rel not in listed and rel not in ("bundle_manifest.json", "publication.json"):
                bad.append(f"unlisted file: {rel}")
    # D258(b): publication record must match its receipt
    if len(bundle_dir.parents) > 5:
        root = bundle_dir.parents[5]
        recs = [r for r in load_receipts(root) if r.get("run_id") == bundle_dir.name]
        pub = bundle_dir / "publication.json"
        for r in recs:
            if not pub.exists():
                bad.append("publication.json missing (a receipt names this run)")
            elif hashlib.sha256(pub.read_bytes()).hexdigest() != r.get("publication_json_sha256"):
                bad.append("publication.json differs from its receipt")
    return bad


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


def anchor_sidecar(anchoring_log_df, lines, anchor_returned_df=None,
                   event_game_map=None, run_id=None):
    """D215(b)/D226/D242/D246: per-game anchor sidecar.

    D242: if anchor_returned_df is provided, use the solver's RETURNED values
    (iterations, converged, anch_m, anch_t) instead of minimizing over the log.
    Market spread/total MUST come from the actual lines dict used by the sim
    (D226: not reconstructed from err fields).
    D246(a): sidecar rows carry event_id (from bundle events) and run_id.
    """
    # D246(a): build game -> event_id map (inverted)
    game_to_event = {}
    if event_game_map:
        for eid, gid in event_game_map.items():
            game_to_event[gid] = eid

    # D257(b): the solver's RETURNED state is mandatory; there is no fallback that
    # minimises over the anchoring log.
    if anchor_returned_df is None:
        raise SystemExit("HALT: anchor_returned.parquet is required — the anchor sidecar "
                         "records what the solver returned, never a reconstruction")
    rows = []
    for _, r in anchor_returned_df.iterrows():
        gname = r["game"]
        ln = lines.get(gname)
        if ln is None:
            raise SystemExit(
                f"HALT: no lines entry for {gname} — anchor sidecar requires "
                f"actual market targets, not reconstructed values")
        spread = float(ln["spread"])
        total_line = float(ln["total"])
        anch_m = float(r["anch_m"])
        anch_t = float(r["anch_t"])
        miss_m = abs(anch_m - spread)
        miss_t = abs(anch_t - total_line)
        row = {
            "game": gname,
            "target_spread": spread, "target_total": total_line,
            "anch_m": round(anch_m, 4), "anch_t": round(anch_t, 4),
            "miss_m": round(miss_m, 4), "miss_t": round(miss_t, 4),
            "iterations": int(r["iterations"]),
            "converged": bool(r["converged"]),
            "anchored": miss_m <= ANCHOR_MISS_TOL and miss_t <= ANCHOR_MISS_TOL,
        }
        if game_to_event:
            row["event_id"] = game_to_event.get(gname, "")
        if run_id is not None:
            row["run_id"] = run_id
        rows.append(row)
    return pd.DataFrame(rows)


def _validate_outputs(run_out, week, run_id, game_ids, bundle_lines=None, bundle_dir=None):
    """D257(b,c): the prediction outputs must belong to THIS run.

    picks_log and anchor_returned must carry season == SEASON, week == week and
    run_id == this run's id on every row; every pick's game must be a bundle game;
    anchor_returned must hold exactly one row per simulated game. Returns
    (picks_log, anchor_returned)."""
    ar_path = run_out / "anchor_returned.parquet"
    if not ar_path.exists():
        raise SystemExit("HALT: anchor_returned.parquet missing — the solver's returned "
                         "anchor state is mandatory (no fallback)")
    picks = pd.read_parquet(run_out / "picks_log.parquet")
    ar = pd.read_parquet(ar_path)
    alog_path = run_out / "anchoring_log.parquet"
    alog = pd.read_parquet(alog_path) if alog_path.exists() else pd.DataFrame()
    want = {"season": SEASON, "week": int(week), "run_id": run_id}
    for name, df in (("picks_log", picks), ("anchor_returned", ar), ("anchoring_log", alog)):
        if len(df) == 0:
            continue
        for col, val in want.items():
            if col not in df.columns:
                raise SystemExit(f"HALT: {name} has no {col} column — output identity unproven")
            vals = df[col].tolist()
            # D260: exact identity — 2026.5 is not 2026, '4' is not 4
            if any(type(v) is bool or v != val or (isinstance(val, int) and float(v) != float(int(v)))
                   for v in vals):
                raise SystemExit(f"HALT: {name} {col} = {sorted(set(map(str, vals)))} "
                                 f"but this run is {col} = {val}")
    gids = set(game_ids)
    if len(picks) and not set(picks["game_id"]).issubset(gids):
        raise SystemExit(f"HALT: picks_log has games outside the bundle: "
                         f"{sorted(set(picks['game_id']) - gids)}")
    if ar["game"].duplicated().any():
        raise SystemExit(f"HALT: anchor_returned has duplicate games: "
                         f"{sorted(ar.loc[ar['game'].duplicated(), 'game'])}")
    if set(ar["game"]) != gids:
        raise SystemExit(f"HALT: anchor_returned games {sorted(set(ar['game']))} != "
                         f"simulated games {sorted(gids)}")
    if bundle_lines is not None:
        # D260: the worker's own record of what it was asked to do must equal the bundle
        inv_path = run_out / "invocation.json"
        if not inv_path.exists():
            raise SystemExit("HALT: invocation.json missing — the worker's inputs are unproven")
        inv = json.loads(inv_path.read_text())
        if inv.get("lines") != bundle_lines or inv.get("games") != sorted(gids) \
                or inv.get("run_id") != run_id or inv.get("week") != int(week) \
                or inv.get("season") != SEASON:
            raise SystemExit("HALT: the worker's invocation.json does not match the bundle "
                             "(lines, games or identity)")
        if bundle_dir is not None:
            # D263 (audit #10 A4): the cutoff the worker claims must be the bundle's, and
            # it must have run against THIS bundle (checked at execution time)
            fr = json.loads((Path(bundle_dir) / "freshness.json").read_text())
            try:
                claimed = _parse_utc(inv.get("cutoff_T"))
            except Exception:
                claimed = None
            if claimed is None or claimed != _parse_utc(fr["cutoff_T"]):
                raise SystemExit(f"HALT: the worker claims cutoff {inv.get('cutoff_T')} but "
                                 f"the bundle's cutoff is {fr['cutoff_T']}")
            if Path(str(inv.get("bundle_dir"))).resolve() != Path(bundle_dir).resolve():
                raise SystemExit(f"HALT: the worker ran against bundle {inv.get('bundle_dir')}, "
                                 f"not {bundle_dir}")
        # D260: the targets the solver RETURNED must be the bundle's targets
        for _, r in ar.iterrows():
            ln = bundle_lines[r["game"]]
            for col, key in (("target_spread", "spread"), ("target_total", "total")):
                if col not in ar.columns or float(r[col]) != float(ln[key]):
                    raise SystemExit(
                        f"HALT: {r['game']} solver target {col} = "
                        f"{r.get(col)} but the bundle's {key} is {ln[key]}")
    return picks, ar


# ── D263: the freeze gate runs OUTSIDE the process that builds and freezes ────────

GATE_TIMEOUT_S = 600
# D266: a primary (non-pilot, non-dry-run) freeze must run in a process started through
# nfl/sim/fwd_bootstrap.py (python3 -I -S -B). Tests that exercise live freezes in-process
# set this False; production code never does.
REQUIRE_LAUNCHER = True

FREEZE_GATE_TESTS = ("test_engine_fingerprint", "test_table_hashes",
                     "test_calibration_hash", "test_params_hash")


def freeze_gate_env(environ=None):
    """The gate's environment: no pytest plugin autoload, no injected plugins/options."""
    env = dict(os.environ if environ is None else environ)
    for k in ("PYTEST_PLUGINS", "PYTEST_ADDOPTS"):
        env.pop(k, None)
    env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    return env


def check_gate_report(xml_text):
    """Exactly the four named freeze tests ran and passed (none failed, errored or
    skipped). An exit code of 0 alone also describes skipped or deselected tests."""
    import xml.etree.ElementTree as ET
    cases = ET.fromstring(xml_text).iter("testcase")
    seen, bad = [], []
    for c in cases:
        name = c.get("name")
        seen.append(name)
        if any(c.find(t) is not None for t in ("failure", "error", "skipped")):
            bad.append(name)
    if sorted(seen) != sorted(FREEZE_GATE_TESTS) or bad:
        raise SystemExit(f"HALT: freeze gate did not pass all four tests: ran={sorted(seen)} "
                         f"not passed={bad}")


def run_freeze_gate():
    """D263 (audit #10 A1): pytest is never imported into this process. A plugin loaded
    in-process could replace harness functions in memory (audit #10 froze 0.97 where the
    sim said 0.62). The gate runs in a fresh subprocess with plugin autoload disabled, and
    its JUnit report must show the four named tests passed."""
    import tempfile
    from nfl.sim import fwd_bootstrap as FB
    with tempfile.TemporaryDirectory() as td:
        xml_path = Path(td) / "gate.xml"
        # D266: the gate child is a bootstrapped process (python3 -I -S -B): no site, no
        # PYTHONPATH, no .pth, no sitecustomize, no stale bytecode; pytest itself and every
        # module it loads are verified against their distribution RECORDs.
        cmd = FB.child_cmd("gate", xml_path)
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT),
                           env=freeze_gate_env(), timeout=GATE_TIMEOUT_S)
        if r.returncode != 0 or not xml_path.exists():
            raise SystemExit(f"HALT: test_freeze_v1 failed (exit {r.returncode}):\n"
                             f"{r.stdout[-2000:]}\n{r.stderr[-2000:]}")
        check_gate_report(xml_path.read_text())


# ── main ──────────────────────────────────────────────────────────────────────

def check_worker_runtime(run_out):
    """D269 (audit #12): the real worker is a bootstrapped process and must leave its own
    verified runtime. HALT if it is missing or not a verified, isolated runtime, or if a
    dependency it shares with this process differs (version, location or RECORD)."""
    p = Path(run_out) / "runtime_worker.json"
    if not p.exists():
        raise SystemExit("HALT: runtime_worker.json missing — the worker's code is unverified")
    rt = json.loads(p.read_text())
    if (rt.get("flags") != "-I -S -B" or not rt.get("pycache_prefix_fresh")
            or not rt.get("n_repo_modules") or not rt.get("n_dependency_files")
            or not rt.get("dependency_distributions")):
        raise SystemExit(f"HALT: the worker's runtime is not a verified isolated runtime: "
                         f"{ {k: rt.get(k) for k in ('flags', 'n_repo_modules', 'n_dependency_files')} }")
    from nfl.sim import fwd_bootstrap as FB
    if FB.ACTIVE:
        mine = FB.verify_loaded_modules()
        if rt.get("python") != mine["python"] or rt.get("executable") != mine["executable"]:
            raise SystemExit("HALT: the worker ran a different interpreter")
        for name, ident in mine["dependency_distributions"].items():
            other = rt["dependency_distributions"].get(name)
            if other is not None and other != ident:
                raise SystemExit(f"HALT: dependency {name} differs between harness and worker")
    return rt


def _default_run_week(root, week, T, bundle_lines, game_ids, run_dir=None,
                      input_dir=None, props_file=None, run_id=None, bundle_dir=None):
    """Default run_week_fn: call run_week.py via subprocess.
    D256/D260: a forward run passes ONLY paths and identity: --bundle-dir (the worker reads
    lines, games and the cutoff from the bundle files, so they enter its read set),
    --input-dir, --props-file, --run-id. No numerical value travels on the command line."""
    if run_dir is not None:
        # D266: the worker is a bootstrapped process (python3 -I -S -B), so its code is
        # executed only from manifest-verified source and its dependencies are verified
        from nfl.sim import fwd_bootstrap as FB
        cmd = FB.child_cmd("worker", "--week", week, "--run-dir", run_dir,
                           "--input-dir", input_dir, "--props-file", props_file,
                           "--run-id", run_id, "--bundle-dir", bundle_dir)
    else:
        cmd = [sys.executable, str(root / "nfl" / "sim" / "run_week.py"), "--week", str(week),
               "--as-of", T.isoformat(), "--lines-json", json.dumps(bundle_lines),
               "--games", ",".join(game_ids)]
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
    # D234: --allow-stale-quotes allowed with --pilot OR --dry-run (never a live freeze)
    if a.allow_stale_quotes and not (a.pilot or a.dry_run):
        raise SystemExit("HALT: --allow-stale-quotes requires --pilot or --dry-run")

    from nfl.sim import fwd_bootstrap as FB
    if REQUIRE_LAUNCHER and not (a.pilot or a.dry_run) and not FB.ACTIVE:
        raise SystemExit("HALT: a primary freeze must be launched as\n"
                         "  python3 -I -S -B nfl/sim/fwd_bootstrap.py harness --week W ...\n"
                         "(D266: no site/.pth/sitecustomize, no PYTHON* env, no stale "
                         "bytecode; repository code only from manifest-verified source)")

    T = datetime.fromisoformat(a.as_of) if a.as_of else datetime.now(timezone.utc)
    if T.tzinfo is None:
        T = T.replace(tzinfo=timezone.utc)

    # (a) test_freeze_v1 + experiment manifest check
    print("(a) Running test_freeze_v1...", flush=True)
    run_freeze_gate()
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

    # D256(c): per-team freshness already HALTed inside build_bundle, on the copies.
    # D256: the calibration stamp and usage fingerprint are checked on the COPIES the
    # prediction will consume, not on the shared files.
    from nfl.sim.read_set import route_inputs
    _restore = route_inputs(bundle_dir / "inputs")
    try:
        stamp_ok, stamp_mismatches = _check_calibration_stamp()
        copy_usage = usage_fingerprint()
    finally:
        _restore()
    if not stamp_ok:
        raise SystemExit("HALT: calibration stamp mismatch on the run's inputs:\n" +
                         "\n".join(f"  {m}" for m in stamp_mismatches))
    if copy_usage != em.get("usage_fingerprint"):
        raise SystemExit(f"HALT: usage fingerprint mismatch on the run's inputs: "
                         f"{copy_usage} != {em.get('usage_fingerprint')}")
    build_manifest = json.loads((bundle_dir / "bundle_manifest.json").read_text())

    # (c) D229: build sheet IN-PROCESS from the bundle's props and lines
    print("(c) Building sheet from bundle...", flush=True)
    from nfl.sim.fwd_v1_logger import build_sheet, set_sport
    set_sport("nfl")
    bundle_props = pd.read_parquet(bundle_dir / "props.parquet")
    bundle_lines_df = pd.read_parquet(bundle_dir / "lines.parquet")
    sheet_df = build_sheet(bundle_props, bundle_lines_df, T)
    # Restrict to the bundle's event_ids
    bundle_eids = set(events_df["event_id"])
    sheet_df = sheet_df[sheet_df["event_id"].isin(bundle_eids)].reset_index(drop=True)
    n_two_way = int(sheet_df["two_way"].sum()) if "two_way" in sheet_df.columns else 0
    print(f"    {len(sheet_df)} lines, {n_two_way} two-way\n", flush=True)

    # D241(b): run_week writes outputs into <run-dir>/outputs/
    run_out = bundle_dir / "outputs"
    run_out.mkdir(exist_ok=True)

    # (d) sim — only the bundle's events
    print("(d) Running sim...", flush=True)
    bundle_lines = lines_dict_from_bundle(bundle_dir)
    game_ids = sorted(bundle_lines.keys())
    bundle_run_id = json.loads((bundle_dir / "freshness.json").read_text()).get("run_id")
    run_week_fn(root, a.week, T, bundle_lines, game_ids, run_dir=run_out,
                input_dir=bundle_dir / "inputs", props_file=bundle_dir / "props.parquet",
                run_id=bundle_run_id, bundle_dir=bundle_dir)
    runtime_worker = None
    if run_week_fn is _default_run_week:
        runtime_worker = check_worker_runtime(run_out)

    # D256(b): read-set proof — every data file the prediction read is in the run
    # directory with the bundle's hash, or a repo file hashed by the experiment manifest
    rs_path = run_out / "read_set.json"
    if not rs_path.exists():
        raise SystemExit("HALT: read_set.json missing — the prediction's inputs are unproven")
    from nfl.sim.read_set import classify_read_set
    rs_summary = classify_read_set(json.loads(rs_path.read_text()), bundle_dir, root,
                                   em["file_hashes"], build_manifest)
    n_i = sum(1 for _, c in rs_summary if c == "i")
    n_ii = sum(1 for _, c in rs_summary if c == "ii")
    print(f"    Read set: {len(rs_summary)} files — {n_i} from the run directory, "
          f"{n_ii} manifest-hashed repo files, 0 unproven", flush=True)

    # D257(b,c): output identity and the solver's returned anchor state
    picks_log, anch_ret = _validate_outputs(run_out, a.week, bundle_run_id, game_ids,
                                            bundle_lines=bundle_lines, bundle_dir=bundle_dir)
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
            mismatches = (joined[0] != joined[1]) & ~(joined[0].isna() & joined[1].isna())
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

    # (f) anchor sidecar — D241(d)/D242/D246(a): use solver's returned values
    print("(f) Building anchor sidecar...", flush=True)
    anch_log_path = run_out / "anchoring_log.parquet"
    if not anch_log_path.exists():
        raise SystemExit("HALT: anchoring_log.parquet missing — sidecar is mandatory (D226)")
    anch_log = pd.read_parquet(anch_log_path)
    # D257(b): anchor_returned (validated above) is the only source of anchor state
    sidecar_df = anchor_sidecar(anch_log, bundle_lines, anchor_returned_df=anch_ret,
                                event_game_map=event_game_map, run_id=bundle_run_id)
    sidecar_path = bundle_dir / "anchor_sidecar.parquet"
    sidecar_df.to_parquet(sidecar_path, index=False)
    n_unanch = int((~sidecar_df["anchored"]).sum())
    print(f"    {len(sidecar_df)} games, {n_unanch} unanchored", flush=True)
    print(sidecar_df.to_string(index=False))

    # D241(f)/D246(b): finalize bundle manifest BEFORE the freeze — hash every file
    _finalize_bundle_manifest(bundle_dir)
    bundle_manifest = json.loads((bundle_dir / "bundle_manifest.json").read_text())
    # D260: reconcile the read set against the FINAL manifest (outputs included)
    classify_read_set(json.loads(rs_path.read_text()), bundle_dir, root,
                      em["file_hashes"], bundle_manifest)

    # D246(b): compute digests BEFORE the freeze, add to filled rows
    experiment_digest = hashlib.sha256(
        (root / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json").read_bytes()
    ).hexdigest()
    bundle_digest = hashlib.sha256(
        (bundle_dir / "bundle_manifest.json").read_bytes()
    ).hexdigest()
    filled["bundle_digest"] = bundle_digest
    filled["experiment_digest"] = experiment_digest

    # dry-run
    if a.dry_run:
        print("\n--- DRY RUN ---")
        print(f"Tag counts:\n{filled['tag'].value_counts().to_string()}")
        print(f"\nBundle manifest: {bundle_dir.relative_to(root)}/bundle_manifest.json")
        print(json.dumps(bundle_manifest, indent=1))
        print("\nDRY RUN complete — nothing frozen.")
        return

    # (g) D241(e)/D246(b): publication is atomic inside freeze()
    print("(g) Freezing...", flush=True)
    from nfl.sim.fwd_v1_logger import freeze as do_freeze
    board_root = root / "nfl" / "data" / "board"
    opinions_dir = board_root / f"week={SEASON}_{a.week:02d}" / "ai_opinions"

    # D241(e): take wall clock immediately before the write
    first_kick = events_df["commence_time"].map(_parse_utc).min()
    if not a.pilot:
        pre_write_wall = datetime.now(timezone.utc)
        if pre_write_wall >= first_kick:
            raise SystemExit(f"HALT: publication time {pre_write_wall.isoformat()} >= "
                         f"first kick {first_kick.isoformat()}")

    # D266: every module loaded in THIS process is verified before it writes the record
    runtime = FB.verify_loaded_modules() if FB.ACTIVE else None

    # D260: the run directory must still be exactly the finalised manifest at the freeze
    vb = verify_bundle(bundle_dir)
    if vb:
        raise SystemExit(f"HALT: run directory changed before the freeze: {vb}")

    # D246(b): frozen parquet written ONCE by freeze() — not rewritten after
    dest, sha, m = do_freeze(
        sheet_df, filled, SEASON, a.week, a.pilot, T,
        d=opinions_dir, reader_model=READER_MODEL, board_root=board_root,
        run_id=bundle_run_id)

    # D241(e)/D246(b): record publication_utc
    publication_utc = datetime.now(timezone.utc)

    # D241(e): quarantine if write completed after kick (live only)
    if not a.pilot and publication_utc >= first_kick:
        quarantine_dir = opinions_dir / "quarantine"
        quarantine_dir.mkdir(parents=True, exist_ok=True)
        quarantine_dest = quarantine_dir / dest.name
        dest.rename(quarantine_dest)
        man_path = opinions_dir / "manifest.json"
        entries = json.loads(man_path.read_text()) if man_path.exists() else []
        for e in entries:
            if e["file"] == dest.name:
                e["excluded"] = True
                e["quarantine_reason"] = (
                    f"publication_utc {publication_utc.isoformat()} >= "
                    f"first_kick {first_kick.isoformat()}")
        man_path.write_text(json.dumps(entries, indent=1) + "\n")
        raise SystemExit(
            f"QUARANTINED: publication at {publication_utc.isoformat()} >= "
            f"first kick {first_kick.isoformat()} — moved to {quarantine_dest}")

    # D246(b): publication.json — written AFTER the freeze, in the run directory
    pub_record = {
        "publication_utc": publication_utc.isoformat(),
        "frozen_file": dest.name,
        "frozen_sha256": sha,
    }
    pub_path = bundle_dir / "publication.json"
    pub_path.write_text(json.dumps(pub_record, indent=1) + "\n")
    archive_file(pub_path, archive_root_for(root))

    # D258(b): the publication receipt — the experiment's own, append-only registry. A
    # frozen file without a receipt is NOT a completed primary freeze.
    receipt = {
        "experiment_id": em.get("experiment_id"),
        "experiment_digest": experiment_digest,
        "run_id": bundle_run_id,
        "bundle_digest": bundle_digest,
        "frozen_file": str(dest.relative_to(root)),
        "frozen_sha256": sha,
        "rows": int(len(m)),
        "publication_utc": publication_utc.isoformat(),
        "first_kick_utc": first_kick.isoformat(),
        "pilot": bool(a.pilot),
        "publication_json_sha256": hashlib.sha256(pub_path.read_bytes()).hexdigest(),
        "run_dir": str(bundle_dir.relative_to(root)),
        # D266: the verified runtime (None = not launched through fwd_bootstrap; only a
        # pilot can be)
        "runtime": FB.verify_loaded_modules() if FB.ACTIVE else None,
        "runtime_before_freeze": runtime,
        "runtime_worker": runtime_worker,
    }
    # D270: a primary records, at freeze time, its dependency drift against the first
    # primary receipt (the experiment's baseline); the first primary IS the baseline
    if not a.pilot:
        first = next((r for r in load_receipts(root) if r.get("pilot") is False), None)
        receipt["dependency_baseline_run_id"] = (first or receipt)["run_id"]
        receipt["dependency_drift"] = dependency_drift(
            [(first or receipt).get(k) for k in RUNTIME_KEYS],
            {k: receipt.get(k) for k in RUNTIME_KEYS})

    # D246(b): update the ai_opinions manifest entry with publication_utc
    man_path = opinions_dir / "manifest.json"
    entries = json.loads(man_path.read_text()) if man_path.exists() else []
    for e in entries:
        if e["file"] == dest.name:
            e["publication_utc"] = publication_utc.isoformat()
            receipt["opinions_manifest_entry"] = e
    man_path.write_text(json.dumps(entries, indent=1) + "\n")

    # D260: the complete record goes to the archive BEFORE the receipt is written:
    # the frozen opinions file and a per-run receipt index (recoverable from the archive
    # alone, even if the repo copy of the run, the frozen file and the registry are lost).
    arch = archive_root_for(root)
    archive_file(dest, arch)
    append_receipt(root, receipt)
    archive_receipt(arch, receipt)
    if (root / RECEIPTS_REL).exists():
        archive_file(root / RECEIPTS_REL, arch)

    print(f"    FROZEN {len(m)} lines -> {dest.relative_to(root)}\n"
          f"    sha256 {sha}\n"
          f"    publication_utc {publication_utc.isoformat()}", flush=True)

    print("\nDone.")
    return dest


if __name__ == "__main__":
    main()
