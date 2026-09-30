#!/usr/bin/env python3
"""The blind opinion log: the reader's probability on EVERY line Hard Rock quotes, frozen pre-kick.

Jeff, 2026-09-21: "grade every single line the hard rock gives against our reasoning... pick a side,
save it to a file, then we'll grade them." He does not look at it. A card, when he asks for one, is
drawn from this log (largest gap to the book, distinct ideas per N58) - the log is never drawn from
a card.

Three steps, all offline (zero API credits; each runs in seconds):
  sheet   the newest pre-kick Hard Rock props pull + game-line snapshot -> one row per quoted line,
          with both prices and the book's de-vigged probability of the FIRST side.
          FIRST side = Over (props, totals) / Yes (anytime TD) / Home team (spreads, h2h).
  freeze  the reader's filled sheet (p_first, tag, reason per line) -> validated, stamped, written
          append-only with a sha256 in the manifest. Refuses: a line with no opinion, a line not in
          the sheet, a game that has kicked off, an existing output file.
  verify  recompute every manifest hash (an edited file fails).

PRE-REGISTERED scoring (written 2026-09-21 before any opinion existed; score step is a later build
and must implement exactly this):
  * Only revision 0 of a line is scored. Later revisions are kept and reported, never scored.
    Revision is counted per reader_model and pilot flag (D219, 2026-09-29).
  * Files frozen with --pilot are never pooled into the record.
  * Two-way lines: Brier and log-loss of p_first vs the book's de-vigged q_first, game-cluster
    bootstrap. One-way lines (anytime TD): vs the vig-inclusive implied price, reported separately.
  * Sides: hit rate AND units at the real Hard Rock price of the side taken (flat -110 is not used).
  * Breakouts: by market, by tag, by |p - q| bucket (<0.03, 0.03-0.08, >0.08), by week, by game.
  * tag 'no_view' rows carry p_first = q_first and take no side; their share is reported every week.
  * P1: Brier(book) <= Brier(reader) on two-way lines. P2: the reader's sides with |p-q| > 0.08 lose
    units at real prices. Both expected to HOLD; the log exists to find where, if anywhere, they fail.

Usage (add --sport ncaaf for the college log: game lines only, Pinnacle as book of record, CFBD finals,
separate output tree ncaaf/data/board/week=<S>_<WW>/ai_opinions/):
  python3 nfl/pipeline/log_ai_opinions.py sheet  --week 2 --out _cowork_patches/ai_sheet.csv
  python3 nfl/pipeline/log_ai_opinions.py freeze --week 2 --filled _cowork_patches/ai_filled.csv --reader-model claude-fable-5-1 [--pilot]
  (freeze re-reads the tape itself; add --props-file/--lines-file for a manual pull, --events "Rams")
  python3 nfl/pipeline/log_ai_opinions.py verify --week 2
  python3 nfl/pipeline/log_ai_opinions.py score  --week 2 [--include-pilot] --out research/.../report.md
"""
import argparse, hashlib, json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# N61: one log per sport, tracked separately. NCAAF has no player props on the tape and Hard Rock is absent
# from 100% of NCAAF snapshots (N01), so the NCAAF book of record is Pinnacle (the CLV benchmark) - its
# de-vigged number is the reference; units are at PINNACLE's price and are labelled so. Jeff bets Hard Rock.
SPORTS = {
    "nfl": {"book": "hardrockbet_fl", "props": ROOT / "data" / "odds_archive" / "nfl" / "props",
            "lines": ROOT / "data" / "odds_archive" / "nfl" / "line_history",
            "out": ROOT / "nfl" / "data" / "board", "outcomes": "pbp",
            "require_side": False},
    "ncaaf": {"book": "pinnacle", "props": None,
              "lines": ROOT / "data" / "odds_archive" / "ncaaf" / "line_history",
              "out": ROOT / "ncaaf" / "data" / "board", "outcomes": "cfbd",
              "require_side": False},
    "nhl": {"book": "pinnacle", "props": None,
            "lines": ROOT / "data" / "odds_archive" / "nhl" / "line_history",
            "out": ROOT / "nhl" / "data" / "board", "outcomes": None,
            "require_side": True},
}
SPORT = "nfl"
BOOK = SPORTS[SPORT]["book"]
PROPS_DIR = SPORTS[SPORT]["props"]
LINES_DIR = SPORTS[SPORT]["lines"]


def set_sport(sport, book=None):
    global SPORT, BOOK, PROPS_DIR, LINES_DIR
    SPORT = sport
    BOOK = book or SPORTS[sport]["book"]
    PROPS_DIR = SPORTS[sport]["props"]
    LINES_DIR = SPORTS[sport]["lines"]
TAGS = ("injury_news", "role_change", "game_script", "matchup", "weather", "price_vs_sharp",
        "usage_trend", "line_move", "no_view", "sim_v1")
KEY = ["event_id", "market_key", "player_name", "line"]
P_MIN, P_MAX = 0.02, 0.98
REASON_MIN, REASON_MAX = 12, 160
NO_VIEW_TOL = 0.005
GAME_MARKETS = ("h2h", "spreads", "totals")


def implied(american):
    a = float(american)
    return 100.0 / (a + 100.0) if a > 0 else -a / (-a + 100.0)


def parse_utc(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def out_dir(season, week):
    return SPORTS[SPORT]["out"] / f"week={season}_{week:02d}" / "ai_opinions"


def _finish(rows, now):
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["imp_first"] = df["price_first"].map(implied)
    df["imp_second"] = df["price_second"].map(lambda x: implied(x) if pd.notna(x) else np.nan)
    df["two_way"] = df["price_second"].notna()
    df["q_first"] = np.where(df["two_way"], df["imp_first"] / (df["imp_first"] + df["imp_second"]), np.nan)
    df["source_age_min"] = df["source_utc"].map(lambda s: round((now - parse_utc(s)).total_seconds() / 60, 1))
    df["player_name"] = df["player_name"].fillna("")
    df["line"] = df["line"].astype(float)
    dup = df.duplicated(KEY, keep=False)
    if dup.any():
        raise SystemExit(f"HALT: duplicate line keys in the pull: {df.loc[dup, KEY].values.tolist()[:5]}")
    return df.sort_values(["commence_time", "event_id", "market_key", "player_name", "line"]).reset_index(drop=True)


def build_sheet(props, lines, now):
    """props: rows of ONE pull per event (the newest); lines: rows of ONE snapshot. Pre-kick only."""
    rows = []
    p = props[(props["bookmaker"] == BOOK) & (props["commence_time"].map(parse_utc) > now)]
    for _, r in p.iterrows():
        if pd.isna(r["over_price"]):
            continue                      # an under-only quote has no first side to price
        rows.append({"event_id": r["event_id"], "commence_time": r["commence_time"],
                     "home_team": r["home_team"], "away_team": r["away_team"],
                     "market_key": r["market_key"], "player_name": r["player_name"],
                     "line": 0.5 if pd.isna(r["line"]) else r["line"],
                     "first_side": "Over", "second_side": "Under",
                     "price_first": r["over_price"], "price_second": r["under_price"],
                     "source_utc": r["pull_timestamp"]})
    g = lines[(lines["bookmaker"] == BOOK) & (lines["market"].isin(GAME_MARKETS))
              & (lines["commence_time"].map(parse_utc) > now)]
    for (eid, mk), s in g.groupby(["event_id", "market"]):
        h = s.iloc[0]
        first = "Over" if mk == "totals" else h["home_team"]
        a = s[s["outcome_name"] == first]
        b = s[s["outcome_name"] != first]
        if len(a) != 1 or len(b) != 1:
            raise SystemExit(f"HALT: {mk} for {h['away_team']} @ {h['home_team']} is not a two-outcome market")
        a, b = a.iloc[0], b.iloc[0]
        rows.append({"event_id": eid, "commence_time": h["commence_time"], "home_team": h["home_team"],
                     "away_team": h["away_team"], "market_key": mk, "player_name": "",
                     "line": 0.0 if pd.isna(a["point"]) else a["point"],
                     "first_side": first, "second_side": b["outcome_name"],
                     "price_first": a["price"], "price_second": b["price"],
                     "source_utc": h["snapshot_utc"]})
    return _finish(rows, now)


def newest_inputs(season, now, props_file=None, lines_file=None):
    """Newest pre-kick Hard Rock pull per event + the newest game-line snapshot, read from the tape.
    props_file / lines_file: a manual pull that has not reached the archive yet (_cowork_patches/)."""
    if PROPS_DIR is None and not props_file:
        props = pd.DataFrame(columns=["event_id", "commence_time", "home_team", "away_team", "bookmaker",
                                      "market_key", "player_name", "line", "over_price", "under_price", "pull_timestamp"])
    else:
        pf = [Path(props_file)] if props_file else sorted((PROPS_DIR / f"season={season}").glob("month=*/data_*.parquet"))[-2:]
        if not pf:
            raise SystemExit("HALT: no props archive for the season")
        props = pd.concat([pd.read_parquet(f) for f in pf], ignore_index=True)
        props = props[props["bookmaker"] == BOOK]
        props = props[props["pull_timestamp"].map(parse_utc) < props["commence_time"].map(parse_utc)]
        # D215(d): cap at now so a pilot with --as-of excludes future pulls
        props = props[props["pull_timestamp"].map(parse_utc) <= now]
        newest = props.groupby("event_id")["pull_timestamp"].transform("max")
        props = props[props["pull_timestamp"] == newest]
    lf = [Path(lines_file)] if lines_file else sorted((LINES_DIR / f"season={season}").glob("snap_*.parquet"))
    if not lf:
        raise SystemExit("HALT: no game-line snapshots for the season")
    if lines_file:
        # D225: bundle already filtered to newest snapshot ≤ T
        lines = pd.read_parquet(lf[0])
        return props, lines[lines["snapshot_utc"] == lines["snapshot_utc"].max()]
    # D225: filter to newest snapshot ≤ T (was: newest regardless of now)
    best_lines = None
    for f in reversed(lf):
        df = pd.read_parquet(f)
        if df.empty:
            continue
        snap_t = parse_utc(df["snapshot_utc"].iloc[0])
        if snap_t <= now:
            best_lines = df
            break
    if best_lines is None:
        raise SystemExit("HALT: no game-line snapshot ≤ now")
    return props, best_lines[best_lines["snapshot_utc"] == best_lines["snapshot_utc"].max()]


def validate(sheet, filled):
    """Returns the frozen frame (no stamps yet). Raises SystemExit on any breach."""
    f = filled.copy()
    f["player_name"] = f["player_name"].fillna("")
    f["line"] = f["line"].astype(float)
    need = set(KEY) | {"p_first", "tag", "reason"}
    # conf and conf_rank are required on all new freezes
    has_conf = "conf" in f.columns and "conf_rank" in f.columns
    if has_conf:
        need |= {"conf", "conf_rank"}
    else:
        raise SystemExit("HALT: filled sheet is missing conf and conf_rank columns "
                         "(required on all new freezes)")
    if need - set(f.columns):
        raise SystemExit(f"HALT: filled sheet is missing columns {sorted(need - set(f.columns))}")
    if f.duplicated(KEY).any():
        raise SystemExit("HALT: filled sheet has duplicate lines")
    merge_cols = KEY + ["p_first", "tag", "reason", "conf", "conf_rank"]
    # D246(b): carry digests through if present
    for dcol in ("bundle_digest", "experiment_digest"):
        if dcol in f.columns:
            merge_cols.append(dcol)
    m = sheet.merge(f[merge_cols], on=KEY, how="outer", indicator=True)
    missing = m[m["_merge"] == "left_only"]
    extra = m[m["_merge"] == "right_only"]
    if len(missing):
        raise SystemExit(f"HALT: {len(missing)} quoted lines have no opinion, e.g. {missing[KEY].values.tolist()[:3]}")
    if len(extra):
        raise SystemExit(f"HALT: {len(extra)} opinions are on lines the book did not quote, e.g. {extra[KEY].values.tolist()[:3]}")
    m = m.drop(columns="_merge")
    if m["p_first"].isna().any() or not m["p_first"].between(P_MIN, P_MAX).all():
        raise SystemExit(f"HALT: p_first must be a number in [{P_MIN}, {P_MAX}] on every line")
    bad = sorted(set(m["tag"]) - set(TAGS))
    if bad:
        raise SystemExit(f"HALT: unknown tag(s) {bad}; allowed {TAGS}")
    # ── conf / conf_rank validation ──
    m["conf"] = pd.to_numeric(m["conf"], errors="coerce")
    m["conf_rank"] = pd.to_numeric(m["conf_rank"], errors="coerce").astype("Int64")
    if m["conf"].isna().any() or not m["conf"].between(0, 100).all():
        raise SystemExit("HALT: conf must be a number in [0, 100] on every line")
    if m["conf_rank"].isna().any():
        raise SystemExit("HALT: conf_rank must be a positive integer on every line")
    if m["conf_rank"].min() != 1 or m["conf_rank"].duplicated().any():
        raise SystemExit("HALT: conf_rank must be unique positive integers starting from 1")
    if set(m["conf_rank"]) != set(range(1, len(m) + 1)):
        raise SystemExit(f"HALT: conf_rank must be 1..{len(m)} with no gaps")

    book = m["q_first"].where(m["two_way"], m["imp_first"])
    nv = m["tag"] == "no_view"
    # D220: no_view must carry clip(book, P_MIN, P_MAX) within NO_VIEW_TOL
    book_clipped = book.clip(P_MIN, P_MAX)
    if ((m["p_first"] - book_clipped).abs()[nv] > NO_VIEW_TOL).any():
        raise SystemExit("HALT: a 'no_view' line must carry clip(book, P_MIN, P_MAX)")
    rl = m["reason"].fillna("").str.len()
    if (~nv & ~rl.between(REASON_MIN, REASON_MAX)).any():
        raise SystemExit(f"HALT: every line with a view needs a reason of {REASON_MIN}-{REASON_MAX} characters")
    m["book_p_first"] = book
    m["gap"] = m["p_first"] - book
    # the side the reader would take; a one-way market has no second side to take
    m["side"] = np.where(nv, "none", np.where(m["gap"] > 0, "first",
                         np.where(m["two_way"], "second", "none")))
    m["side_name"] = np.where(m["side"] == "first", m["first_side"],
                              np.where(m["side"] == "second", m["second_side"], ""))
    m["side_price"] = np.where(m["side"] == "first", m["price_first"],
                               np.where(m["side"] == "second", m["price_second"], np.nan))
    # ── NHL (and any require_side sport): refuse side "none" ──
    if SPORTS[SPORT].get("require_side", False):
        nones = m[m["side"] == "none"]
        if len(nones):
            raise SystemExit(f"HALT: {SPORT} requires a side on every line; "
                             f"{len(nones)} lines have side='none' "
                             f"(no_view tag or gap==0 on a one-way market)")
    # ── edge: reader probability of its side minus book's de-vigged probability ──
    reader_side_p = np.where(m["side"] == "first", m["p_first"],
                             np.where(m["side"] == "second", 1 - m["p_first"], np.nan))
    book_side_p = np.where(m["side"] == "first", m["book_p_first"],
                           np.where(m["side"] == "second", 1 - m["book_p_first"], np.nan))
    m["edge"] = np.where(m["side"] == "none", 0.0, reader_side_p - book_side_p)
    return m


def prior_revisions(d, reader_model=None, pilot=None):
    """Count revisions from earlier files of the SAME reader_model AND pilot flag.

    FWD1c (D219): a new file's revision counts only earlier files with the same
    reader_model and the same pilot flag. An entry with no reader_model key counts
    as reader "legacy", which matches nothing new. Scoring is unchanged: revision 0
    means each reader's first opinion on a line (2026-09-29).
    """
    manifest_path = d / "manifest.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else []
    own_files = set()
    for entry in manifest:
        entry_rm = entry.get("reader_model", "legacy")
        entry_pilot = entry.get("pilot", False)
        if entry_rm == reader_model and entry_pilot == bool(pilot):
            own_files.add(entry["file"])
    seen = {}
    for f in sorted(d.glob("ai_opinions_*.parquet")):
        if f.name not in own_files:
            continue
        for *k, rev in pd.read_parquet(f)[KEY + ["revision"]].itertuples(index=False, name=None):
            seen[tuple(k)] = max(seen.get(tuple(k), -1), int(rev))
    return seen


def freeze(sheet, filled, season, week, pilot, now, d=None, reader_model=None,
           board_root=None, run_id=None):
    """sheet MUST come from build_sheet() in this process: prices are read from the tape at freeze
    time, never from a CSV the reader could have touched.
    N62: reader_model (the model that formed the opinions, e.g. 'claude-fable-5-1') is REQUIRED and is
    written on every row and into the manifest - the reader is part of the research object."""
    if not reader_model or not str(reader_model).strip():
        raise SystemExit("HALT: --reader-model is required (the model that made these picks)")
    # D224(c): canonicalize reader string (strip whitespace)
    reader_model = str(reader_model).strip()
    d = d or out_dir(season, week)
    # D224a: cross-week dedup for canonical (non-pilot) reader.
    # A contract already frozen in ANY week directory (including current) is refused.
    if not pilot:
        board_root = board_root or SPORTS[SPORT]["out"]
        contracts = [(r["event_id"], r["market_key"], r["player_name"], float(r["line"]))
                     for _, r in filled.iterrows()]
        dupes = []
        contract_set = set(contracts)
        for wd in sorted(board_root.glob(f"week={season}_*/ai_opinions")):
            manifest_path = wd / "manifest.json"
            if not manifest_path.exists():
                continue
            manifest = json.loads(manifest_path.read_text())
            for entry in manifest:
                rm = entry.get("reader_model", "legacy")
                if rm != reader_model or entry.get("pilot", False):
                    continue
                f = wd / entry["file"]
                if not f.exists():
                    continue
                try:
                    edf = pd.read_parquet(f, columns=KEY)
                except Exception:
                    continue
                for _, r in edf.iterrows():
                    key = (r["event_id"], r["market_key"], r["player_name"], float(r["line"]))
                    if key in contract_set:
                        dupes.append((key, wd.parent.name))
        if dupes:
            raise SystemExit(
                f"HALT: {len(dupes)} contract(s) already frozen (cross-week dedup):\n"
                + "\n".join(f"  {c} in {w}" for c, w in dupes[:10]))
    late = sheet[sheet["commence_time"].map(parse_utc) <= now]
    if len(late):
        raise SystemExit(f"HALT: {late['event_id'].nunique()} game(s) in the sheet have kicked off - nothing is frozen")
    m = validate(sheet, filled)
    d.mkdir(parents=True, exist_ok=True)
    seen = prior_revisions(d, reader_model=reader_model, pilot=pilot)
    m["revision"] = [seen.get((r.event_id, r.market_key, r.player_name, r.line), -1) + 1
                     for r in m.itertuples(index=False)]
    m["season"], m["week"], m["pilot"] = season, week, bool(pilot)
    m["sport"], m["book"] = SPORT, BOOK
    m["reader_model"] = str(reader_model).strip()
    m["logged_utc"] = now.isoformat()
    # D230: run_id links frozen rows to their sim run's bundle
    if run_id is not None:
        m["run_id"] = run_id
    dest = d / f"ai_opinions_{now.strftime('%Y%m%dT%H%M%SZ')}.parquet"
    if dest.exists():
        raise SystemExit(f"HALT: {dest.name} exists - the log is append-only")
    m.to_parquet(dest, index=False)
    sha = hashlib.sha256(dest.read_bytes()).hexdigest()
    man = d / "manifest.json"
    entries = json.loads(man.read_text()) if man.exists() else []
    entries.append({"file": dest.name, "sha256": sha, "logged_utc": now.isoformat(), "rows": len(m),
                    "sport": SPORT, "book": BOOK, "reader_model": str(reader_model).strip(),
                    "pilot": bool(pilot), "games": int(m["event_id"].nunique()),
                    "no_view_share": round(float((m["tag"] == "no_view").mean()), 3),
                    "revised_rows": int((m["revision"] > 0).sum()),
                    "oldest_source_age_min": float(m["source_age_min"].max()),
                    "first_kickoff_utc": str(m["commence_time"].min())})
    man.write_text(json.dumps(entries, indent=1) + "\n")
    return dest, sha, m


def verify(season, week, d=None):
    d = d or out_dir(season, week)
    man = d / "manifest.json"
    entries = json.loads(man.read_text()) if man.exists() else []
    bad = [e["file"] for e in entries
           if not (d / e["file"]).exists() or hashlib.sha256((d / e["file"]).read_bytes()).hexdigest() != e["sha256"]]
    unlisted = sorted({f.name for f in d.glob("ai_opinions_*.parquet")} - {e["file"] for e in entries})
    return entries, bad, unlisted


# ----------------------------------------------------------------------------- score
STAT_OF = {"player_receptions": ("rec", "actual_rec"), "player_reception_yds": ("rec", "actual_rec_yds"),
           "player_rush_attempts": ("rush", "actual_carries"), "player_rush_yds": ("rush", "actual_rush_yds"),
           "player_anytime_td": ("td", "actual_atd"), "player_pass_attempts": ("pass", "actual_pass_att"),
           "player_pass_completions": ("pass", "actual_completions"), "player_pass_yds": ("pass", "actual_pass_yds"),
           "player_pass_tds": ("pass", "actual_pass_td")}
GAP_BUCKETS = [(-1, 0.03, "<0.03"), (0.03, 0.08, "0.03-0.08"), (0.08, 9, ">0.08")]


def _load_snap_participants(season):
    """D236: load snap counts from nflreadpy. Returns {game_id: {"pfr_ids": set, "names": set}}
    where a player played = offense_snaps + st_snaps > 0.
    Returns None if snap data is unavailable for the season."""
    try:
        import nflreadpy
        sc = nflreadpy.load_snap_counts([season])
        if hasattr(sc, "to_pandas"):
            sc = sc.to_pandas()  # polars -> pandas
        if sc.empty:
            return None
    except Exception:
        return None
    # played = offense + special teams snaps > 0
    sc["_played"] = (sc["offense_snaps"].fillna(0) + sc["st_snaps"].fillna(0)) > 0
    played = sc[sc["_played"]]
    result = {}
    for gid, gdf in played.groupby("game_id"):
        result[gid] = {
            "pfr_ids": set(gdf["pfr_player_id"].dropna().str.strip().values),
            "names": set(gdf["player"].str.strip().values),
        }
    return result


def _build_gsis_to_pfr(season):
    """D236(b): GSIS ID -> PFR ID crosswalk from nflverse roster."""
    try:
        import nflreadpy
        roster = nflreadpy.load_rosters([season])
        if hasattr(roster, "to_pandas"):
            roster = roster.to_pandas()
        if roster.empty:
            return {}
    except Exception:
        return {}
    valid = roster[roster["gsis_id"].notna() & roster["pfr_id"].notna()]
    return dict(zip(valid["gsis_id"].str.strip(), valid["pfr_id"].str.strip()))


def _game_actuals(pbp, home, away):
    """Actual per-player stats and the final score for one game, from the repo's own PBP reader.
    D236(c): returns None for incomplete games (no END GAME row)."""
    from nfl.sim.actuals import actual_player_game_stats
    from nfl.sim.names import FULL_TO_ABBR
    h, a = FULL_TO_ABBR.get(home, home), FULL_TO_ABBR.get(away, away)
    g = pbp[(pbp["home_team"] == h) & (pbp["away_team"] == a)]
    if g.empty:
        return None
    # D236(c): completed-game check
    completed = g["desc"].str.contains("END GAME", case=False, na=False).any()
    if not completed:
        return None
    rec, rush, td, pas = actual_player_game_stats(g)
    tabs = {"rec": rec, "rush": rush, "td": td, "pass": pas}
    ints = g[g["play_type"] == "pass"].groupby("passer_player_id")["interception"].sum()
    return {"tabs": tabs, "ints": ints, "home_pts": float(g["home_score"].max()),
            "away_pts": float(g["away_score"].max()), "home": h, "away": a,
            "n_plays": len(g)}


def _game_actuals_by_id(pbp, game_id):
    """D243(c): game actuals by nflverse game_id (e.g. '2026_03_CAR_KC')."""
    from nfl.sim.actuals import actual_player_game_stats
    g = pbp[pbp["game_id"] == game_id]
    if g.empty:
        return None
    completed = g["desc"].str.contains("END GAME", case=False, na=False).any()
    if not completed:
        return None
    rec, rush, td, pas = actual_player_game_stats(g)
    tabs = {"rec": rec, "rush": rush, "td": td, "pass": pas}
    ints = g[g["play_type"] == "pass"].groupby("passer_player_id")["interception"].sum()
    return {"tabs": tabs, "ints": ints,
            "home_pts": float(g["home_score"].max()),
            "away_pts": float(g["away_score"].max()),
            "home": str(g["home_team"].iloc[0]),
            "away": str(g["away_team"].iloc[0]),
            "n_plays": len(g)}


def _load_nflverse_schedule(season):
    """D243(c): load nflverse schedule for mapping team pairs to game_ids."""
    try:
        import nflreadpy
        sched = nflreadpy.load_schedules([season])
        if hasattr(sched, "to_pandas"):
            sched = sched.to_pandas()
        return sched
    except Exception:
        return pd.DataFrame()


def _event_to_game_id(event_id, home_abbr, away_abbr, season, week, schedule):
    """D243(c): map a frozen event_id to the nflverse game_id via schedule.

    Uses the schedule for the specific season and week — a week-3 game with the
    same team pair as a week-4 game does NOT match.
    """
    if schedule is None or schedule.empty:
        # No schedule loaded -> cannot do exact-event grading
        return None
    # Filter schedule to the exact week
    wk = schedule[(schedule["season"] == season) & (schedule["week"] == week)]
    if wk.empty:
        return None  # No games in this week
    # Find the game with matching home/away
    match = wk[(wk["home_team"] == home_abbr) & (wk["away_team"] == away_abbr)]
    if len(match) == 1:
        return str(match["game_id"].iloc[0])
    if len(match) == 0:
        return None  # No game in this week -> unresolved
    # Ambiguous -> None
    return None


def _cfbd_actuals(season):
    """NCAAF finals from the CFBD games file, via the ticket grader's own loader and name map (N41)."""
    from ncaaf.pipeline.grade_ncaaf_tickets import _load_cfbd_outcomes, _odds_to_cfbd
    outcomes, teams = _load_cfbd_outcomes(season)

    def game(home, away, commence):
        h, a = _odds_to_cfbd(home, teams), _odds_to_cfbd(away, teams)
        if h is None or a is None:
            return None
        cands = [g for g in outcomes.get(frozenset((h, a)), []) if g["completed"]]
        if not cands:
            return None
        k = parse_utc(commence)
        g = min(cands, key=lambda g: abs((g["start"] - k).total_seconds()))
        if abs((g["start"] - k).total_seconds()) > 36 * 3600:
            return None
        return {"home_pts": float(g["points"][h]), "away_pts": float(g["points"][a]), "tabs": {}, "ints": pd.Series(dtype=float)}
    return game


def _first_side_won(row, act, pid, snap_played=None):
    """1 if the FIRST side of the line happened, 0 if not, None for a push / unresolved / VOID.
    D230: snap_played is a tri-state: True (played), False (VOID), None (snap data unavailable = unresolved)."""
    mk, line = row["market_key"], float(row["line"])
    if mk == "h2h":
        return 1 if act["home_pts"] > act["away_pts"] else (0 if act["home_pts"] < act["away_pts"] else None)
    if mk == "spreads":                      # first side = home team at `line`
        m = act["home_pts"] + line - act["away_pts"]
        return None if m == 0 else int(m > 0)
    if mk == "totals":
        t = act["home_pts"] + act["away_pts"]
        return None if t == line else int(t > line)
    if pid is None:
        return None
    # D236(a): snap-count participation check
    if snap_played is False:
        return None  # VOID: player did not play (not in snap counts)
    if snap_played is None:
        return None  # UNRESOLVED: no snap data for this game
    if mk == "player_pass_interceptions":
        v = float(act["ints"].get(pid, 0.0))
    else:
        tab, col = STAT_OF[mk]
        t = act["tabs"][tab]
        r = t[t["player_id"] == pid]
        v = float(r[col].iloc[0]) if len(r) else 0.0
    if mk == "player_anytime_td":
        return int(v > 0)
    return None if v == line else int(v > line)


def _reader_models(m, d):
    """N62: the model that made each file's picks. Files frozen after N62 carry a reader_model column;
    earlier files are attributed in reader_attribution.json ({file: model}) beside the manifest -
    frozen files are never edited. Anything unattributed reads 'unknown', never a guess."""
    side = d / "reader_attribution.json"
    att = json.loads(side.read_text()) if side.exists() else {}
    col = m["reader_model"] if "reader_model" in m.columns else pd.Series(np.nan, index=m.index)
    return col.where(col.notna() & (col.astype(str) != ""), m["_file"].map(att)).fillna("unknown")


def score(season, week, d=None, include_pilot=False, pbp_path=None):
    """The pre-registered scoring in the module docstring, applied to revision-0 rows."""
    from nfl.sim.names import load_roster, _build_roster_lookup, resolve_player, FULL_TO_ABBR
    d = d or out_dir(season, week)
    files = sorted(d.glob("ai_opinions_*.parquet"))
    if not files:
        raise SystemExit("HALT: no frozen opinion files")
    m = pd.concat([pd.read_parquet(f).assign(_file=f.name) for f in files], ignore_index=True)
    m["reader_model"] = _reader_models(m, d)
    m = m[m["revision"] == 0]
    if not include_pilot:
        m = m[~m["pilot"]]
    if m.empty:
        raise SystemExit("HALT: nothing to score (pilot files need --include-pilot)")
    if SPORTS[SPORT]["outcomes"] == "cfbd":
        cfbd = _cfbd_actuals(season)
        pbp, lk = None, None
    else:
        pbp = pd.read_parquet(pbp_path or ROOT / "nfl" / "data" / "pbp" / f"pbp_{season}.parquet")
        lk = _build_roster_lookup(load_roster(), season, week)
    # D236: load snap-count participants and GSIS->PFR crosswalk
    snap_parts = _load_snap_participants(season)
    gsis_to_pfr = _build_gsis_to_pfr(season)
    n_id_match = n_name_match = 0
    rows = []
    for (home, away), s in m.groupby(["home_team", "away_team"]):
        if pbp is None:
            act = cfbd(home, away, s["commence_time"].iloc[0])
        else:
            act = _game_actuals(pbp, home, away)
        teams = [FULL_TO_ABBR.get(home, home), FULL_TO_ABBR.get(away, away)]
        h_abbr, a_abbr = FULL_TO_ABBR.get(home, home), FULL_TO_ABBR.get(away, away)
        nfl_game_id = f"{season}_{week:02d}_{a_abbr}_{h_abbr}"
        game_snap = snap_parts.get(nfl_game_id) if snap_parts else None
        for _, r in s.iterrows():
            settlement = "settled"
            if act is None:
                y, pid, method = None, None, "game not in PBP"
                settlement = "unresolved"
            elif r["player_name"]:
                pid, method = resolve_player(r["player_name"], season, week, teams, *lk)
                # D236(b): match by player ID (GSIS -> PFR), fall back to name
                if game_snap is None:
                    snap_played = None
                else:
                    pfr_id = gsis_to_pfr.get(pid) if pid else None
                    if pfr_id and pfr_id in game_snap["pfr_ids"]:
                        snap_played = True
                        n_id_match += 1
                    elif r["player_name"].strip() in game_snap["names"]:
                        snap_played = True
                        n_name_match += 1
                    elif pid is None or pfr_id is None:
                        # D243(d): crosswalk missing -> UNRESOLVED, not VOID
                        snap_played = None
                    else:
                        # ID resolved AND absent from snap counts -> VOID
                        snap_played = False
                y = _first_side_won(r, act, pid, snap_played=snap_played)
                if y is None and pid is not None:
                    if snap_played is False:
                        settlement = "void"
                    elif snap_played is None:
                        settlement = "unresolved"
                    else:
                        settlement = "unresolved"  # push or stat missing
                elif y is None:
                    settlement = "unresolved"
            else:
                pid, method, y = None, "game", _first_side_won(r, act, None)
                if y is None:
                    settlement = "unresolved"
            rows.append({**r.to_dict(), "player_id": pid, "resolve": method,
                         "y_first": y, "settlement": settlement})
    out = pd.DataFrame(rows)
    out["graded"] = out["y_first"].notna()
    out["side_won"] = np.where(out["side"] == "first", out["y_first"] == 1,
                               np.where(out["side"] == "second", out["y_first"] == 0, False))
    dec = out["side_price"].map(lambda a: (a / 100 + 1) if pd.notna(a) and a > 0 else (100 / -a + 1) if pd.notna(a) else np.nan)
    out["units"] = np.where(out["side"] == "none", 0.0, np.where(out["graded"], np.where(out["side_won"], dec - 1, -1.0), 0.0))
    out["gap_bucket"] = pd.cut(out["gap"].abs(), [b[0] for b in GAP_BUCKETS] + [9], labels=[b[2] for b in GAP_BUCKETS], right=False)
    # ── conf band (for files that carry conf) ──
    if "conf_rank" in out.columns and out["conf_rank"].notna().any():
        out["conf_band"] = pd.cut(out["conf_rank"], bins=[0, 10, 25, 50, 9999],
                                  labels=["1-10", "11-25", "26-50", "51+"], right=True)
        # edge_rank: rank by descending edge (1 = largest edge)
        if "edge" in out.columns and out["edge"].notna().any():
            out["edge_rank"] = out["edge"].rank(ascending=False, method="first").astype("Int64")
    # ── postfreeze CSV (reporting cut only — never changes a grade or removes a row) ──
    pf_files = sorted(d.glob("postfreeze_*.csv")) if d else []
    if pf_files:
        pf = pd.concat([pd.read_csv(f) for f in pf_files], ignore_index=True)
        # Match rows: postfreeze file has a "rows affected" column listing event_ids
        # Mark rows that are touched by post-freeze news
        affected_events = set()
        if "game" in pf.columns:
            affected_events = set(pf["game"].dropna().unique())
        out["postfreeze_affected"] = out["event_id"].isin(affected_events) if affected_events else False
    else:
        out["postfreeze_affected"] = False
    return out


def score_report(out, season, week):
    g = out[out["graded"]].copy()
    two = g[g["two_way"]]
    one = g[~g["two_way"]]
    L = [f"# Blind opinion log - score, {SPORT.upper()} {season} week {week} (book of record: {BOOK})", "",
         f"files: {sorted(out['_file'].unique())}; pilot rows included: {bool(out['pilot'].any())}",
         f"rows {len(out)}, graded {len(g)} (pushes/unresolved {int((~out['graded']).sum())}), "
         f"with a view {int((g['tag'] != 'no_view').sum())}, no_view share {(out['tag'] == 'no_view').mean():.1%}", "",
         "**A pilot or a single game is a log, not evidence. Nothing is tuned on it.**", ""]
    def bl(s):
        return f"reader {brier_(s['p_first'], s['y_first']):.4f} / book {brier_(s['book_p_first'], s['y_first']):.4f}"
    if len(two):
        L += [f"## Two-way lines (n={len(two)}): Brier reader vs de-vigged book: {bl(two)} - "
              f"P1 (book <= reader) {'HELD' if brier_(two['book_p_first'], two['y_first']) <= brier_(two['p_first'], two['y_first']) else 'DID NOT HOLD'}"]
        v = two[two["tag"] != "no_view"]
        if len(v):
            L += [f"   lines with a view only (n={len(v)}): {bl(v)}"]
    if len(one):
        L += [f"## One-way lines (n={len(one)}): Brier reader vs vig-inclusive implied: {bl(one)}"]
    sides = g[g["side"] != "none"]
    if len(sides):
        L += ["", f"## Sides taken (n={len(sides)}): {int(sides['side_won'].sum())} won, units at real price "
              f"{sides['units'].sum():+.2f} ({sides['units'].sum() / len(sides):+.3f}/leg)"]
        big = sides[sides["gap"].abs() > 0.08]
        if len(big):
            L += [f"   |p-q| > 0.08 (n={len(big)}): {int(big['side_won'].sum())} won, units {big['units'].sum():+.2f} - "
                  f"P2 (lose units) {'HELD' if big['units'].sum() < 0 else 'DID NOT HOLD'}"]
        breakout_cols = ["reader_model", "market_key", "tag", "gap_bucket"]
        if "conf_band" in sides.columns and sides["conf_band"].notna().any():
            breakout_cols.append("conf_band")
        for col in breakout_cols:
            t = sides.groupby(col, observed=True).agg(n=("units", "size"), won=("side_won", "sum"), units=("units", "sum")).round(2)
            L += ["", f"### by {col}", "", t.to_markdown()]
        # ── conf_rank vs edge_rank comparison ──
        if "conf_rank" in sides.columns and "edge_rank" in sides.columns and sides["conf_rank"].notna().any():
            L += ["", "### conf_rank vs edge_rank"]
            L += ["", "Do the reader's top-ranked picks (by conf) outperform a ranking by raw edge?"]
            for band, lo, hi in [("1-10", 1, 10), ("11-25", 11, 25), ("26-50", 26, 50), ("51+", 51, 99999)]:
                by_conf = sides[sides["conf_rank"].between(lo, hi)]
                by_edge = sides[sides["edge_rank"].between(lo, hi)]
                if len(by_conf) == 0 and len(by_edge) == 0:
                    continue
                conf_u = by_conf["units"].sum() if len(by_conf) else 0
                edge_u = by_edge["units"].sum() if len(by_edge) else 0
                L += [f"  band {band}: conf_rank n={len(by_conf)} units={conf_u:+.2f}  |  "
                      f"edge_rank n={len(by_edge)} units={edge_u:+.2f}  |  "
                      f"{'conf wins' if conf_u > edge_u else 'edge wins' if edge_u > conf_u else 'tie'}"]
    # ── postfreeze reporting cut ──
    if "postfreeze_affected" in g.columns and g["postfreeze_affected"].any():
        touched = g[g["postfreeze_affected"]]
        untouched = g[~g["postfreeze_affected"]]
        L += ["", "## Post-freeze news cut (reporting only — no grades changed)",
              f"  touched: {len(touched)} rows, {int(touched['side_won'].sum())} won, "
              f"units {touched['units'].sum():+.2f}",
              f"  untouched: {len(untouched)} rows, {int(untouched['side_won'].sum())} won, "
              f"units {untouched['units'].sum():+.2f}"]
    detail_cols = ["market_key", "player_name", "line", "side_name", "side_price", "book_p_first",
                   "p_first", "y_first", "side_won", "units", "tag"]
    if "conf" in g.columns:
        detail_cols.insert(-1, "conf")
    if "conf_rank" in g.columns:
        detail_cols.insert(-1, "conf_rank")
    if "edge" in g.columns:
        detail_cols.insert(-1, "edge")
    L += ["", "## Every line with a view", "",
          g[g["tag"] != "no_view"][[c for c in detail_cols if c in g.columns]].round(3).to_markdown(index=False)]
    return "\n".join(L) + "\n"


def brier_(p, y):
    return float(np.mean((np.asarray(p, float) - np.asarray(y, float)) ** 2))


# ── D227: primary cohort and scoring ─────────────────────────────────────────

ELIGIBLE_MARKETS = {"player_receptions", "player_rush_attempts"}
COHORT_PREDICATE = (
    "reader == canonical, non-pilot, first freeze of contract (revision 0), "
    "tag sim_v1, two_way, market in {player_receptions, player_rush_attempts}, "
    "game anchored per bundle, settled (not void or unresolved)"
)


def primary_cohort(scored_df, canonical_reader, sidecar):
    """D227/D246(a): filter scored rows to the primary experiment cohort.

    D246(a): sidecar is a DataFrame with (run_id, event_id, anchored). Each
    candidate row is joined on (run_id, event_id) — exactly one sidecar row
    per pair. Missing or duplicate -> HALT (SystemExit).

    Returns (cohort_df, exclusions) where exclusions is a dict of reason -> count.
    """
    df = scored_df.copy()
    n_start = len(df)
    exclusions = {}

    def _exclude(mask, reason):
        n = int(mask.sum())
        if n > 0:
            exclusions[reason] = n
        return ~mask

    # Reader == canonical, non-pilot
    keep = _exclude(df["reader_model"] != canonical_reader, "reader != canonical")
    keep &= _exclude(df["pilot"].astype(bool), "pilot")
    # First freeze (revision 0)
    keep &= _exclude(df["revision"] != 0, "revision > 0")
    # Tag sim_v1
    keep &= _exclude(df["tag"] != "sim_v1", "tag != sim_v1")
    # Two-way
    keep &= _exclude(~df["two_way"].astype(bool), "not two_way")
    # Market in eligible set
    keep &= _exclude(~df["market_key"].isin(ELIGIBLE_MARKETS), "market not eligible")

    # D246(a): anchor join on (run_id, event_id) — exactly one sidecar row per pair
    if "run_id" not in df.columns or "event_id" not in df.columns:
        raise SystemExit("HALT: scored rows missing run_id or event_id — cannot join sidecar")
    if not sidecar.empty and ("run_id" not in sidecar.columns or "event_id" not in sidecar.columns):
        raise SystemExit("HALT: sidecar missing run_id or event_id columns")
    if sidecar.empty:
        # All rows excluded — no sidecar data at all
        keep &= _exclude(pd.Series(True, index=df.index), "no sidecar match")
    else:
        # Check for duplicates in sidecar
        sc_key = sidecar[["run_id", "event_id"]]
        dupes = sc_key.duplicated(keep=False)
        if dupes.any():
            raise SystemExit(
                f"HALT: {int(dupes.sum())} duplicate sidecar rows on (run_id, event_id)")
        # Join
        sc_lookup = sidecar.set_index(["run_id", "event_id"])["anchored"]
        candidate_keys = list(zip(df["run_id"].values, df["event_id"].values))
        anchored_flags = []
        for rid, eid in candidate_keys:
            key = (rid, eid)
            if key not in sc_lookup.index:
                anchored_flags.append(None)
            else:
                anchored_flags.append(bool(sc_lookup.loc[key]))
        df["_anchored"] = anchored_flags
        missing_sidecar = df["_anchored"].isna()
        keep &= _exclude(missing_sidecar, "no sidecar match")
        keep &= _exclude(df["_anchored"] == False, "game not anchored")
        df = df.drop(columns=["_anchored"], errors="ignore")

    # Settled (not void or unresolved)
    if "settlement" in df.columns:
        keep &= _exclude(df["settlement"] != "settled", "not settled")
    else:
        keep &= _exclude(~df["graded"], "not graded")

    cohort = df[keep].copy()
    exclusions["_total_excluded"] = n_start - len(cohort)
    return cohort, exclusions


def primary_statistic(cohort_df, n_bootstrap=50000, seed=20261004):
    """D227: Δ = mean[(p-y)^2 - (q-y)^2], whole-game bootstrap.

    Returns dict with n_legs, n_games, delta, ci_lo, ci_hi, verdict.
    """
    if cohort_df.empty:
        return {"n_legs": 0, "n_games": 0, "delta": None,
                "ci_lo": None, "ci_hi": None, "verdict": "insufficient data"}

    df = cohort_df.copy()
    # D243(e): cluster by event_id (not by team pair)
    if "event_id" in df.columns:
        games = df["event_id"].values
    else:
        from nfl.sim.names import FULL_TO_ABBR
        df["_game_id"] = df.apply(
            lambda r: f"{FULL_TO_ABBR.get(r['away_team'], r['away_team'])}@"
                      f"{FULL_TO_ABBR.get(r['home_team'], r['home_team'])}", axis=1)
        games = df["_game_id"].values

    p = df["p_first"].values.astype(float)
    q = df["book_p_first"].values.astype(float)
    y = df["y_first"].values.astype(float)

    # Point estimate
    delta_leg = (p - y) ** 2 - (q - y) ** 2
    delta = float(np.mean(delta_leg))

    # Whole-game bootstrap
    unique_games = np.unique(games)
    n_games = len(unique_games)
    rng = np.random.RandomState(seed)
    deltas = np.empty(n_bootstrap)
    game_indices = {g: np.where(games == g)[0] for g in unique_games}

    for b in range(n_bootstrap):
        sampled_games = rng.choice(unique_games, size=n_games, replace=True)
        idx = np.concatenate([game_indices[g] for g in sampled_games])
        deltas[b] = np.mean(delta_leg[idx])

    ci_lo, ci_hi = float(np.percentile(deltas, 2.5)), float(np.percentile(deltas, 97.5))

    if ci_hi < 0:
        verdict = "superior"  # model Brier < book Brier
    elif ci_lo > 0:
        verdict = "inferior"
    else:
        verdict = "inconclusive"

    return {
        "n_legs": len(df), "n_games": n_games,
        "delta": round(delta, 6), "ci_lo": round(ci_lo, 6), "ci_hi": round(ci_hi, 6),
        "verdict": verdict,
    }


def score_experiment(experiment, canonical_reader, season=2026, include_pilot=False,
                     single_file=None):
    """D230/D243: score an experiment across all week directories.

    D243(a): validates experiment name against manifest, verifies hashes, selects
    canonical non-pilot revision-0 rows. Skips weeks with no eligible rows.
    D243(b): anchor join by (run_id, event_id) — exactly one sidecar row per pair.
    D243(c): exact-event grading via nflverse schedule (event_id -> game_id).
    D243(d): crosswalk missing -> UNRESOLVED, not VOID.
    D243(e): bootstrap clusters by event_id; checkpoint policy.
    """
    from nfl.sim.names import load_roster, _build_roster_lookup, resolve_player, FULL_TO_ABBR
    from nfl.sim.run_forward_v1 import verify_bundle

    board_root = SPORTS["nfl"]["out"]

    # D243(a): validate experiment name against manifest
    em_path = ROOT / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json"
    if not em_path.exists():
        raise SystemExit("HALT: experiment manifest not found")
    em = json.loads(em_path.read_text())
    if em.get("experiment_id") != experiment:
        raise SystemExit(f"HALT: unregistered experiment '{experiment}' "
                         f"(manifest has '{em.get('experiment_id')}')")

    all_scored = []

    if single_file:
        # Score one file regardless of revision, labelled as diagnostic
        f = Path(single_file)
        if not f.exists():
            raise SystemExit(f"HALT: file {single_file} not found")
        # D243(a): verify the frozen file's hash
        parent_dir = f.parent
        man_path = parent_dir / "manifest.json"
        if man_path.exists():
            manifest_entries = json.loads(man_path.read_text())
            for e in manifest_entries:
                if e["file"] == f.name:
                    expected_sha = e["sha256"]
                    actual_sha = hashlib.sha256(f.read_bytes()).hexdigest()
                    if actual_sha != expected_sha:
                        raise SystemExit(
                            f"HALT: frozen file hash mismatch: {f.name} "
                            f"({actual_sha[:16]} != {expected_sha[:16]})")
                    break

        m = pd.read_parquet(f).assign(_file=f.name)
        if "reader_model" not in m.columns:
            m["reader_model"] = "unknown"
        week = int(m["week"].iloc[0]) if "week" in m.columns else 0
        pbp_path = ROOT / "nfl" / "data" / "pbp" / f"pbp_{season}.parquet"
        if not pbp_path.exists():
            raise SystemExit(f"HALT: PBP file {pbp_path} not found")
        pbp = pd.read_parquet(pbp_path)

        # D243(c): load nflverse schedule for exact event_id -> game_id mapping
        schedule = _load_nflverse_schedule(season)

        lk = _build_roster_lookup(load_roster(), season, week)
        snap_parts = _load_snap_participants(season)
        gsis_to_pfr = _build_gsis_to_pfr(season)
        rows = []
        for _, r in m.iterrows():
            settlement = "settled"
            home, away = r["home_team"], r["away_team"]
            h_abbr = FULL_TO_ABBR.get(home, home)
            a_abbr = FULL_TO_ABBR.get(away, away)

            # D243(c): exact-event grading — map event_id to game_id via schedule
            nfl_game_id = _event_to_game_id(r.get("event_id"), h_abbr, a_abbr,
                                             season, week, schedule)
            if nfl_game_id is None:
                # No schedule match -> unresolved
                rows.append({**r.to_dict(), "player_id": None, "resolve": "no schedule match",
                             "y_first": None, "settlement": "unresolved"})
                continue

            act = _game_actuals_by_id(pbp, nfl_game_id)
            teams = [h_abbr, a_abbr]
            game_snap = snap_parts.get(nfl_game_id) if snap_parts else None
            if act is None:
                y, pid, method = None, None, "game not in PBP"
                settlement = "unresolved"
            elif r["player_name"]:
                pid, method = resolve_player(r["player_name"], season, week, teams, *lk)
                if game_snap is None:
                    snap_played = None
                else:
                    pfr_id = gsis_to_pfr.get(pid) if pid else None
                    if pfr_id and pfr_id in game_snap["pfr_ids"]:
                        snap_played = True
                    elif r["player_name"].strip() in game_snap["names"]:
                        snap_played = True
                    else:
                        snap_played = False
                    # D243(d): crosswalk missing -> UNRESOLVED, not VOID
                    if pid is None and snap_played is False:
                        snap_played = None  # no crosswalk -> unresolved

                y = _first_side_won(r, act, pid, snap_played=snap_played)
                if y is None and pid is not None:
                    settlement = "void" if snap_played is False else "unresolved"
                elif y is None:
                    settlement = "unresolved"
            else:
                pid, method, y = None, "game", _first_side_won(r, act, None)
                settlement = "unresolved" if y is None else "settled"
            rows.append({**r.to_dict(), "player_id": pid, "resolve": method,
                         "y_first": y, "settlement": settlement})
        scored = pd.DataFrame(rows)
        scored["graded"] = scored["y_first"].notna()
        scored["side_won"] = np.where(scored["side"] == "first", scored["y_first"] == 1,
                                       np.where(scored["side"] == "second", scored["y_first"] == 0, False))
        dec = scored["side_price"].map(lambda a: (a / 100 + 1) if pd.notna(a) and a > 0 else (100 / -a + 1) if pd.notna(a) else np.nan)
        scored["units"] = np.where(scored["side"] == "none", 0.0,
                                    np.where(scored["graded"], np.where(scored["side_won"], dec - 1, -1.0), 0.0))
        print(f"[DIAGNOSTIC — NOT THE RECORD: {f.name}]")
        print(f"  Total rows: {len(scored)}, graded: {scored['graded'].sum()}")
        sim_rows = scored[(scored["tag"] == "sim_v1") & scored["graded"]]
        if "book_p_first" in sim_rows.columns and len(sim_rows) > 0:
            diag_stat = primary_statistic(sim_rows)
            print(f"  sim_v1 settled: {len(sim_rows)} legs, {diag_stat['n_games']} games")
            print(f"  Δ = {diag_stat['delta']:.6f}" if diag_stat['delta'] is not None else "  Δ = n/a")
            if diag_stat['ci_lo'] is not None:
                print(f"  95% CI: [{diag_stat['ci_lo']:.6f}, {diag_stat['ci_hi']:.6f}]")
            print(f"  Verdict: {diag_stat['verdict']}")
            big = sim_rows[sim_rows["gap"].abs() > 0.08]
            if len(big) > 0:
                p2_units = big["units"].sum()
                print(f"  P2 (|p-q|>0.08): {len(big)} legs, units = {p2_units:+.2f}")
        all_scored.append(scored)
    else:
        # Pool ALL week directories
        for wd in sorted(board_root.glob(f"week={season}_*/ai_opinions")):
            week_str = wd.parent.name.split("_")[-1]
            try:
                week = int(week_str)
            except ValueError:
                continue
            # D243(a): verify every frozen file and bundle
            entries_ok, bad, unlisted = verify(season, week, d=wd)
            if bad:
                raise SystemExit(f"HALT: hash mismatch in week {week}: {bad}")
            # Verify bundles
            sim_runs_dir = wd.parent / "sim_runs"
            if sim_runs_dir.exists():
                for rd in sim_runs_dir.iterdir():
                    if rd.is_dir():
                        vbad = verify_bundle(rd)
                        if vbad:
                            raise SystemExit(f"HALT: bundle verify failed for {rd.name}: {vbad}")

            # D243(a): select canonical, non-pilot, revision-0 rows
            files = sorted(wd.glob("ai_opinions_*.parquet"))
            if not files:
                print(f"  week {week}: no frozen files, skipping")
                continue
            week_df = pd.concat([pd.read_parquet(f).assign(_file=f.name) for f in files],
                                ignore_index=True)
            week_df["reader_model"] = _reader_models(week_df, wd)
            # Select eligible rows BEFORE grading
            eligible = week_df[
                (week_df["reader_model"] == canonical_reader) &
                (~week_df["pilot"].astype(bool)) &
                (week_df["revision"] == 0)
            ]
            if eligible.empty:
                print(f"  week {week}: 0 eligible rows (all pilot or non-canonical), skipping")
                continue
            try:
                scored = score(season, week, d=wd, include_pilot=False)
                all_scored.append(scored)
            except SystemExit as e:
                if "nothing to score" in str(e):
                    print(f"  week {week}: {e}")
                    continue
                raise

    # D243(a): 0 eligible legs is a valid result, not an abort
    if not all_scored:
        n_eligible = 0
    else:
        pooled = pd.concat(all_scored, ignore_index=True)
        n_eligible = len(pooled)

    # D246(a): Load anchor sidecars from bundles — each carries (run_id, event_id)
    # D246(b): verify bundle BEFORE loading sidecar; check bundle_digest of frozen rows
    all_sidecars = []
    bundle_digests = {}  # run_id -> sha256(bundle_manifest.json)
    for wd in sorted(board_root.glob(f"week={season}_*/sim_runs/*/anchor_sidecar.parquet")):
        run_id = wd.parent.name
        # D246(a): verify the bundle BEFORE loading sidecar
        vbad = verify_bundle(wd.parent)
        if vbad:
            raise SystemExit(f"HALT: bundle verify failed for {wd.parent.name}: {vbad}")
        sc = pd.read_parquet(wd)
        if "run_id" not in sc.columns:
            sc["run_id"] = run_id
        all_sidecars.append(sc)
        # D246(b): record bundle_digest for row-level verification
        man_path = wd.parent / "bundle_manifest.json"
        if man_path.exists():
            bundle_digests[run_id] = hashlib.sha256(man_path.read_bytes()).hexdigest()
    sidecar_df = pd.concat(all_sidecars, ignore_index=True) if all_sidecars else pd.DataFrame()

    # D246(b): verify frozen rows' bundle_digest against actual bundle
    if all_scored and bundle_digests:
        pooled_check = pd.concat(all_scored, ignore_index=True) if len(all_scored) > 1 else all_scored[0]
        if "bundle_digest" in pooled_check.columns and "run_id" in pooled_check.columns:
            for rid, expected_bd in bundle_digests.items():
                rows_for_run = pooled_check[pooled_check["run_id"] == rid]
                if rows_for_run.empty:
                    continue
                row_bd = rows_for_run["bundle_digest"].dropna().unique()
                for bd_val in row_bd:
                    if bd_val != expected_bd:
                        raise SystemExit(
                            f"HALT: frozen row bundle_digest {str(bd_val)[:16]} != "
                            f"actual bundle {expected_bd[:16]} for run {rid}")

    if n_eligible == 0:
        # D243(e): checkpoint policy — below 500 eligible legs -> descriptive only
        print(f"\n0 eligible legs — descriptive only, no verdict.")
        return

    cohort, exclusions = primary_cohort(pooled, canonical_reader, sidecar=sidecar_df)

    print(f"\nCohort predicate: {COHORT_PREDICATE}")
    print(f"\nExclusions:")
    for reason, count in sorted(exclusions.items()):
        if reason != "_total_excluded":
            print(f"  {reason}: {count}")
    print(f"  TOTAL excluded: {exclusions.get('_total_excluded', 0)}")
    print(f"  Cohort: {len(cohort)} legs")

    if cohort.empty:
        print("\n0 eligible legs — descriptive only, no verdict.")
        return

    stat = primary_statistic(cohort)

    # D243(e): checkpoint policy
    n_legs = stat["n_legs"]
    if n_legs < 500:
        print(f"\n{n_legs} eligible legs (< 500) — descriptive only, no verdict.")
        print(f"  Δ = {stat['delta']:.6f}")
        if stat['ci_lo'] is not None:
            print(f"  95% CI: [{stat['ci_lo']:.6f}, {stat['ci_hi']:.6f}]")
        return

    print(f"\nPrimary statistic (Δ = mean[(p-y)² - (q-y)²]):")
    print(f"  Δ = {stat['delta']:.6f}")
    print(f"  95% CI: [{stat['ci_lo']:.6f}, {stat['ci_hi']:.6f}]")
    if n_legs >= 1500:
        print(f"  Verdict: {stat['verdict']}  [CONFIRMATORY — n={n_legs} >= 1500]")
    else:
        print(f"  Verdict: descriptive only (n={n_legs} < 1500)")
    print(f"  n_legs = {stat['n_legs']}, n_games = {stat['n_games']}")

    # P2
    if "book_p_first" in cohort.columns and "side_price" in cohort.columns:
        p2 = cohort[cohort["gap"].abs() > 0.08].copy()
        if len(p2) > 0:
            dec = p2["side_price"].map(lambda a: (a / 100 + 1) if pd.notna(a) and a > 0 else (100 / -a + 1) if pd.notna(a) else np.nan)
            p2_units = np.where(p2["side"] == "none", 0.0,
                                np.where(p2["graded"], np.where(p2["side_won"], dec - 1, -1.0), 0.0))
            print(f"\nP2 (|p-q| > 0.08, settled): {len(p2)} legs, units = {float(np.sum(p2_units)):+.2f}")
        else:
            print("\nP2: no legs with |p-q| > 0.08")

    # Breakouts
    for col in ["market_key", "week"]:
        if col in cohort.columns:
            grp = cohort.groupby(col).agg(n=("units", "size"),
                                            won=("side_won", "sum"),
                                            units=("units", "sum")).round(2)
            print(f"\nBreakout by {col}:")
            print(grp.to_string())

    if "gap" in cohort.columns:
        cohort["_gap_bucket"] = pd.cut(cohort["gap"].abs(), [0, 0.03, 0.08, 9],
                                        labels=["<0.03", "0.03-0.08", ">0.08"], right=False)
        grp = cohort.groupby("_gap_bucket", observed=True).agg(
            n=("units", "size"), won=("side_won", "sum"), units=("units", "sum")).round(2)
        print(f"\nBreakout by gap bucket:")
        print(grp.to_string())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sheet", "freeze", "verify", "score", "score-experiment"])
    ap.add_argument("--sport", choices=list(SPORTS), default="nfl")
    ap.add_argument("--book", default=None, help="override the sport's book of record")
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--week", type=int, default=None)
    ap.add_argument("--out"), ap.add_argument("--filled")
    ap.add_argument("--props-file"), ap.add_argument("--lines-file")
    ap.add_argument("--events", help="comma list of team-name fragments; default every pre-kick game")
    ap.add_argument("--window-hours", type=float, help="only games kicking off within this many hours")
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--reader-model", help="REQUIRED for freeze (N62): the model that made the picks, e.g. claude-fable-5-1")
    ap.add_argument("--include-pilot", action="store_true"), ap.add_argument("--pbp")
    ap.add_argument("--as-of", help="UTC ISO timestamp (pilot only); errors without --pilot")
    ap.add_argument("--experiment", help="experiment id for score-experiment")
    ap.add_argument("--file", help="score one file (diagnostic mode)")
    a = ap.parse_args()
    if a.as_of and not a.pilot:
        sys.exit("HALT: --as-of requires --pilot")
    set_sport(a.sport, a.book)
    now = datetime.fromisoformat(a.as_of) if a.as_of else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    if a.cmd in ("sheet", "freeze"):
        sheet = build_sheet(*newest_inputs(a.season, now, a.props_file, a.lines_file), now)
        if a.events and len(sheet):
            fr = [x.strip().lower() for x in a.events.split(",")]
            sheet = sheet[(sheet.home_team + " " + sheet.away_team).str.lower().map(lambda t: any(x in t for x in fr))]
        if a.window_hours and len(sheet):
            hrs = sheet["commence_time"].map(lambda c: (parse_utc(c) - now).total_seconds() / 3600)
            sheet = sheet[hrs <= a.window_hours]
        if sheet.empty:
            sys.exit("HALT: no pre-kick Hard Rock lines found")
    if a.cmd == "sheet":
        Path(a.out).parent.mkdir(parents=True, exist_ok=True)
        sheet.to_csv(a.out, index=False)
        print(f"{len(sheet)} lines, {sheet.event_id.nunique()} game(s), two-way {int(sheet.two_way.sum())} -> {a.out}")
        print(sheet.groupby(["away_team", "home_team"])["source_age_min"].agg(["count", "min", "max"]).to_string())
    elif a.cmd == "freeze":
        dest, sha, m = freeze(sheet, pd.read_csv(a.filled), a.season, a.week, a.pilot, now,
                             reader_model=a.reader_model)
        print(f"FROZEN {len(m)} lines -> {dest.relative_to(ROOT)}\nsha256 {sha}\n"
              f"pilot={a.pilot} no_view={(m.tag == 'no_view').mean():.1%} oldest source {m.source_age_min.max()} min")
    elif a.cmd == "score":
        if a.week is None:
            sys.exit("HALT: --week is required for score")
        entries, bad, unlisted = verify(a.season, a.week)
        if bad or unlisted:
            sys.exit(f"HALT: manifest check failed before scoring: {bad or unlisted}")
        out = score(a.season, a.week, include_pilot=a.include_pilot, pbp_path=a.pbp)
        text = score_report(out, a.season, a.week)
        print(text)
        if a.out:
            Path(a.out).write_text(text)
            out.to_parquet(Path(a.out).with_suffix(".parquet"), index=False)
    elif a.cmd == "score-experiment":
        if not a.experiment:
            sys.exit("HALT: --experiment is required for score-experiment")
        # Load canonical reader from the experiment manifest
        em_path = ROOT / "research" / "nfl_sim" / "FWD_EXPERIMENT_v1.json"
        if not em_path.exists():
            sys.exit(f"HALT: experiment manifest not found: {em_path}")
        em = json.loads(em_path.read_text())
        canonical = em.get("canonical_reader", "")
        score_experiment(a.experiment, canonical, season=a.season,
                        include_pilot=a.include_pilot, single_file=a.file)
    elif a.cmd == "verify":
        if a.week is None:
            sys.exit("HALT: --week is required for verify")
        entries, bad, unlisted = verify(a.season, a.week)
        print(f"{len(entries)} frozen file(s); hash mismatch/missing: {bad or 'none'}; not in manifest: {unlisted or 'none'}")
        if bad or unlisted:
            sys.exit(1)


if __name__ == "__main__":
    main()
