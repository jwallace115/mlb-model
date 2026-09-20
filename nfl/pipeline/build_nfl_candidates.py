#!/usr/bin/env python3
"""
N43: NFL prop CANDIDATE TABLE and ticket log — the written-down half of the NFL ticket.

No simulation, no model, no edge claim. Everything that can be a rule is a rule here; what is
left to a reader (news, injuries to OTHER players, weather) is logged as a veto with a source.

  1. Hard Rock props: the newest pull at or before build_time, pre-kick rows only
     (production drop_inplay_rows), games that have not kicked.
  2. Two-way markets are de-vigged from the SAME ROW (same book, same pull). One-way markets
     (anytime TD) are listed and never eligible: no complement, no probability.
  3. Roles from nfl/data/sim/ratings/player_usage_weekly.parquet (season, week), matched on
     normalised name within the game's two teams. No match = `role_unmatched`, never dropped.
  4. ESPN injury status from the newest archive file pulled at or before build_time.
  5. D58 MOVED-AGAINST: this week's first pull vs the pull used. Displayed, never acted on.
  6. ELIGIBLE = volume family AND two-way AND role matched AND not Out/Doubtful/IR AND the
     pull is fresh. The pick side is the side the book favours (de-vigged q >= 0.5).
  7. BASELINE TICKET = the top-K eligible legs by q, one per game. Pure rule, reproducible.
     The reader's final ticket (log_final_ticket / --final) is assembled by code from candidate
     rows; its departures from both baselines are DERIVED and each needs a reason and a source;
     every final leg needs its own availability confirmation. Fewer than K legs, or none, is valid.

Outputs (paths relative to the repo root):
  nfl/data/board/week=<season>_<ww>/nfl_prop_candidates_<UTC>.parquet  + .md
  nfl/data/board/nfl_prop_tickets_<season>.json   append-only, (build_time, ticket_id) keyed
"""

import argparse
import gzip
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from nfl.pipeline.pull_hardrock_props import drop_inplay_rows  # noqa: E402
from nfl.sim.names import FULL_TO_ABBR, _normalise  # noqa: E402

PROPS_DIR = ROOT / "data" / "odds_archive" / "nfl" / "props"
USAGE_PATH = ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet"
INJURY_DIR = ROOT / "data" / "injury_archive" / "nfl"
BOARD_DIR = ROOT / "nfl" / "data" / "board"

BOOK = "hardrockbet_fl"
# Families whose underlying attribute passed the split-half reliability audit (D11, 2021-24:
# carry share r 0.98, target share 0.94). Yardage and TD families did not; they are listed only.
VOLUME_FAMILIES = ("player_receptions", "player_rush_attempts",
                   "player_pass_attempts", "player_pass_completions")
ROLE_COLUMN = {"player_receptions": "target_share", "player_rush_attempts": "carry_share",
               "player_pass_attempts": "is_starting_qb", "player_pass_completions": "is_starting_qb"}
UNAVAILABLE = ("Out", "Doubtful", "Injured Reserve", "Suspension", "Physically Unable to Perform")
# The Sunday slots are 15:00Z and 16:30Z; a 17:00Z-kick ticket built after inactives (15:30Z)
# reads a pull up to ~1.75 h old. Older than this and the table is a record, not a board.
MAX_PULL_AGE_HOURS = 3.0
# N44: the ESPN injury feed runs every 6 h (health check allows 7). An older file says nothing
# about today: on 2026-09-19 fixtures an August-1 file still admitted 50 legs.
MAX_INJURY_AGE_HOURS = 7.0
TOP_K = 5
# NFL 2026 opened Thu 2026-09-10; weeks run Tuesday to Monday.
SEASON_WEEK1_TUESDAY = {2026: "2026-09-08"}


def _utc(ts):
    t = pd.Timestamp(ts)
    return t.tz_localize("UTC") if t.tzinfo is None else t.tz_convert("UTC")


def nfl_week(season, when):
    start = _utc(SEASON_WEEK1_TUESDAY[season])
    return int((_utc(when) - start).days // 7) + 1


def american_to_decimal(odds):
    odds = float(odds)
    return 1 + odds / 100 if odds > 0 else 1 + 100 / abs(odds)


def american_to_implied(odds):
    return 1.0 / american_to_decimal(odds)


def load_props(props_dir, season, build_time):
    """All Hard Rock rows pulled at or before build_time, pre-kick only (production filter)."""
    frames = [pd.read_parquet(f) for f in sorted(Path(props_dir).glob(f"season={season}/month=*/*.parquet"))]
    if not frames:
        raise RuntimeError(f"HALT: no props partitions under {props_dir}/season={season}")
    df = pd.concat(frames, ignore_index=True)
    df = df[df["bookmaker"] == BOOK]
    rows = drop_inplay_rows(df.to_dict("records"))
    df = pd.DataFrame(rows)
    df["pull_dt"] = df["pull_timestamp"].map(_utc)
    df["commence_dt"] = df["commence_time"].map(_utc)
    return df[df["pull_dt"] <= _utc(build_time)].copy()


def board_rows(props, build_time):
    """Rows of the newest pull for games that have not kicked; plus that week's first pull."""
    bt = _utc(build_time)
    live = props[props["commence_dt"] > bt]
    if live.empty:
        raise RuntimeError("HALT: no un-kicked games in the props archive at build_time")
    newest = live["pull_dt"].max()
    board = live[live["pull_dt"] == newest].copy()
    week_start = bt.normalize() - pd.Timedelta(days=(bt.dayofweek - 1) % 7)
    earlier = live[(live["pull_dt"] < newest) & (live["pull_dt"] >= week_start)]
    first = (earlier.sort_values("pull_dt")
             .drop_duplicates(["event_id", "player_name", "market_key"], keep="first"))
    return board, first, newest


def load_injuries(injury_dir, season, build_time):
    """{(team abbr, normalised name): status} from the newest file pulled <= build_time."""
    bt = _utc(build_time)
    best, best_when = None, None
    for f in sorted(Path(injury_dir).glob(f"season={season}/injuries_*.json*")):
        stamp = f.name.split("_")[1].split(".")[0]
        when = pd.Timestamp(datetime.strptime(stamp, "%Y%m%dT%H%MZ"), tz="UTC")
        if when <= bt:
            best, best_when = f, when
    if best is None:
        raise RuntimeError(f"HALT: no injury file at or before {build_time}")
    opener = gzip.open if best.suffix == ".gz" else open
    with opener(best, "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    teams = data["injuries"]
    if len(teams) != 32:
        raise RuntimeError(f"HALT: {best.name} holds {len(teams)} teams, expected 32")
    status = {}
    for team in teams:
        abbr = FULL_TO_ABBR.get(team.get("displayName"))
        if abbr is None:
            raise RuntimeError(f"HALT: unknown team in {best.name}: {team.get('displayName')}")
        for item in team.get("injuries", []):
            name = _normalise(item.get("athlete", {}).get("displayName", ""))
            if name:
                status[(abbr, name)] = item.get("status", "")   # keyed by TEAM and name
    return status, best.name, max(best_when, _confirmed_unchanged_until(best.parent, bt, best_when))


def _confirmed_unchanged_until(season_dir, bt, file_when):
    """N46: the ESPN puller hash-skips — an unchanged feed writes a `_pulls.jsonl` line, not a
    file. The newest file is current as of the last pull that logged the SAME sha256."""
    pulls = season_dir / "_pulls.jsonl"
    if not pulls.exists():
        return file_when
    lines = []
    for raw in pulls.read_text().splitlines():
        try:
            e = json.loads(raw)
            when = pd.Timestamp(datetime.strptime(e["utc"], "%Y%m%dT%H%MZ"), tz="UTC")
        except (ValueError, KeyError, TypeError):
            continue
        if e.get("feed", "espn_injuries") == "espn_injuries" and "file" not in e and when <= bt:
            lines.append((when, e.get("sha256"), e.get("status")))
    written = [l for l in lines if l[2] == "written" and l[0] <= file_when + pd.Timedelta(minutes=5)]
    if not written:
        return file_when
    sha = max(written)[1]
    later = [l[0] for l in lines if l[1] == sha]
    # any LATER line with a different sha means the content changed and its file should exist
    changed_after = [l[0] for l in lines if l[1] != sha and l[0] > max(written)[0]]
    return file_when if changed_after else max(later)


def build_candidates(props_dir=PROPS_DIR, usage_path=USAGE_PATH, injury_dir=INJURY_DIR,
                     season=2026, build_time=None, max_pull_age_hours=MAX_PULL_AGE_HOURS,
                     max_injury_age_hours=MAX_INJURY_AGE_HOURS):
    build_time = build_time or datetime.now(timezone.utc).isoformat()
    props = load_props(props_dir, season, build_time)
    board, first, newest = board_rows(props, build_time)
    pull_age_h = (_utc(build_time) - newest).total_seconds() / 3600
    week = nfl_week(season, board["commence_dt"].min())

    usage = pd.read_parquet(usage_path)
    usage = usage[(usage["season"] == season) & (usage["week"] == week)].copy()
    if usage["team"].nunique() != 32:
        raise RuntimeError(f"HALT: usage has {usage['team'].nunique()} teams for {season} wk{week}")
    usage["_key"] = usage["player_name"].map(_normalise)
    # Rank within the team, from the usage table itself (not only players with a prop).
    # N44: ties take the WORST rank — four players tied on a prior are not four lead receivers.
    usage["target_rank"] = usage.groupby("team")["target_share"].rank(ascending=False, method="max")
    usage["carry_rank"] = usage.groupby("team")["carry_share"].rank(ascending=False, method="max")
    injuries, injury_file, injury_when = load_injuries(injury_dir, season, build_time)
    injury_age_h = (_utc(build_time) - injury_when).total_seconds() / 3600

    first_key = first.set_index(["event_id", "player_name", "market_key"])
    out = []
    for r in board.to_dict("records"):
        teams = (FULL_TO_ABBR[r["home_team"]], FULL_TO_ABBR[r["away_team"]])
        key = _normalise(r["player_name"])
        role = usage[(usage["_key"] == key) & usage["team"].isin(teams)]
        two_way = pd.notna(r["under_price"]) and pd.notna(r["over_price"]) and pd.notna(r["line"])
        row = {
            "event_id": r["event_id"], "commence_time": r["commence_time"],
            "home_team": r["home_team"], "away_team": r["away_team"],
            "player_name": r["player_name"], "market_key": r["market_key"], "line": r["line"],
            "over_price": r["over_price"], "under_price": r["under_price"],
            "pull_timestamp": r["pull_timestamp"], "two_way": bool(two_way),
            "volume_family": r["market_key"] in VOLUME_FAMILIES,
            "role_matched": len(role) == 1,
            "team": role.iloc[0]["team"] if len(role) == 1 else None,
            "position": role.iloc[0]["position"] if len(role) == 1 else None,
            "target_share": float(role.iloc[0]["target_share"]) if len(role) == 1 else None,
            "carry_share": float(role.iloc[0]["carry_share"]) if len(role) == 1 else None,
            "is_starting_qb": bool(role.iloc[0]["is_starting_qb"]) if len(role) == 1 else None,
            "target_rank": float(role.iloc[0]["target_rank"]) if len(role) == 1 else None,
            "carry_rank": float(role.iloc[0]["carry_rank"]) if len(role) == 1 else None,
            # N44: the player's OWN team only (it used to search the opponent too)
            "injury_status": injuries.get((role.iloc[0]["team"], key)) if len(role) == 1 else None,
            "n_targets": int(role.iloc[0]["n_targets"]) if len(role) == 1 else None,
            "n_carries": int(role.iloc[0]["n_carries"]) if len(role) == 1 else None,
        }
        if two_way:
            io, iu = american_to_implied(r["over_price"]), american_to_implied(r["under_price"])
            row["hold"] = io + iu - 1.0
            row["q_over"] = io / (io + iu)
            row["pick_side"] = "Over" if row["q_over"] >= 0.5 else "Under"
            row["q_pick"] = max(row["q_over"], 1 - row["q_over"])
            row["pick_price"] = r["over_price"] if row["pick_side"] == "Over" else r["under_price"]
            row["complement_price"] = r["under_price"] if row["pick_side"] == "Over" else r["over_price"]
            k = (r["event_id"], r["player_name"], r["market_key"])
            if k in first_key.index:
                f = first_key.loc[k]
                if pd.notna(f["under_price"]) and pd.notna(f["line"]):
                    fo, fu = american_to_implied(f["over_price"]), american_to_implied(f["under_price"])
                    row["first_pull_timestamp"] = f["pull_timestamp"]
                    row["line_first"] = float(f["line"])
                    row["q_over_first"] = fo / (fo + fu)
                    # D58, on the raw implied of the picked side, same line only
                    if float(f["line"]) == float(r["line"]):
                        then = fo if row["pick_side"] == "Over" else fu
                        now = io if row["pick_side"] == "Over" else iu
                        row["moved_against"] = bool(then < now)
        reasons = []
        if not row["volume_family"]:
            reasons.append("not_volume_family")
        if not two_way:
            reasons.append("one_way_no_devig")
        if not row["role_matched"]:
            reasons.append("role_unmatched")
        elif row["market_key"] in VOLUME_FAMILIES:
            col = ROLE_COLUMN[row["market_key"]]
            if col == "is_starting_qb" and not row["is_starting_qb"]:
                reasons.append("not_flagged_starting_qb")
        if row["injury_status"] in UNAVAILABLE:
            reasons.append(f"status_{row['injury_status']}")
        if pull_age_h > max_pull_age_hours:
            reasons.append("pull_stale")
        if injury_age_h > max_injury_age_hours:
            reasons.append("injury_feed_stale")
        # No entry in ESPN's feed is NOT evidence of availability (healthy stars have none;
        # so does a mis-spelt name). It stays eligible and is flagged: every final leg needs
        # an availability source of its own (log_final_ticket).
        row["feed_status_missing"] = row["injury_status"] is None
        row["ineligible_reasons"] = ";".join(reasons)
        row["eligible"] = not reasons
        out.append(row)

    cand = pd.DataFrame(out)
    meta = {
        "build_time": str(build_time), "season": season, "week": week,
        "props_pull_timestamp": newest.isoformat(), "props_pull_age_hours": round(pull_age_h, 3),
        "props_rows": int(len(board)), "events": int(board["event_id"].nunique()),
        "usage_sha256": hashlib.sha256(Path(usage_path).read_bytes()).hexdigest(),
        "injury_file": injury_file, "injury_file_age_hours": round(injury_age_h, 3),
        "devig_method": "proportional_same_row", "policy": "N44",
    }
    return cand, meta


def baseline_ticket(cand, top_k=TOP_K):
    """Top-K eligible legs by de-vigged probability, ONE PER GAME. Ties: price, then name."""
    e = cand[cand["eligible"]].sort_values(
        ["q_pick", "pick_price", "player_name", "market_key"],
        ascending=[False, False, True, True])
    e = e.drop_duplicates("event_id", keep="first").head(top_k)
    return [leg_record(r) for r in e.to_dict("records")]


def role_overs_ticket(cand, top_k=TOP_K):
    """Second written baseline: Overs the book favours, on a team's lead roles only —
    a top-2 target share for receptions, the top carry share for rush attempts, the flagged
    starting QB for attempts/completions. Ranks within team, so no threshold to tune."""
    e = cand[cand["eligible"] & (cand["pick_side"] == "Over")]
    lead = (((e["market_key"] == "player_receptions") & (e["target_rank"] <= 2))
            | ((e["market_key"] == "player_rush_attempts") & (e["carry_rank"] == 1))
            | (e["market_key"].isin(["player_pass_attempts", "player_pass_completions"])
               & (e["is_starting_qb"] == True)))  # noqa: E712
    e = e[lead].sort_values(["q_pick", "pick_price", "player_name", "market_key"],
        ascending=[False, False, True, True])
    e = e.drop_duplicates("event_id", keep="first").head(top_k)
    return [leg_record(r) for r in e.to_dict("records")]


def leg_record(r):
    return {k: (None if pd.isna(r.get(k)) else r.get(k)) for k in (
        "event_id", "commence_time", "home_team", "away_team", "player_name", "team",
        "market_key", "line", "pick_side", "pick_price", "complement_price", "q_pick",
        "hold", "pull_timestamp", "target_share", "carry_share", "target_rank", "carry_rank",
        "n_targets", "n_carries", "injury_status", "feed_status_missing", "moved_against")}


def ticket_price(legs):
    """Cross-game parlay = product of the legs (16 of 16 Hard Rock slips, N-series ledger)."""
    dec = 1.0
    for leg in legs:
        dec *= american_to_decimal(leg["pick_price"])
    fair = 1.0
    for leg in legs:
        fair *= leg["q_pick"]
    return {"decimal": round(dec, 3), "product_of_devigged_q": round(fair, 5),
            "expected_return_per_1_at_book_q": round(dec * fair, 4)}


LEG_KEY = ("event_id", "player_name", "market_key")
LEG_IDENTITY = ("event_id", "player_name", "market_key", "line", "pick_side", "pick_price",
                "complement_price", "pull_timestamp")


def _key(leg):
    return tuple(leg[k] for k in LEG_KEY)


def check_legs_against_candidates(legs, cand, max_per_game=1):
    """N44: a logged leg IS a candidate row — same line, side, both prices, same pull — it is
    eligible, and a ticket holds one leg per game. (N43's logger took two copies of one leg at
    an invented 999.5 line and +9999.)"""
    seen_events, seen_players = {}, set()
    for leg in legs:
        for field in LEG_IDENTITY:
            if leg.get(field) is None:
                raise RuntimeError(f"HALT: leg missing {field}: {leg}")
        m = cand[(cand["event_id"] == leg["event_id"]) & (cand["player_name"] == leg["player_name"])
                 & (cand["market_key"] == leg["market_key"])]
        if len(m) != 1:
            raise RuntimeError(f"HALT: leg is not exactly one candidate row: {_key(leg)}")
        row = m.iloc[0]
        for field in ("line", "pick_side", "pick_price", "complement_price", "pull_timestamp"):
            if row[field] != leg[field]:
                raise RuntimeError(f"HALT: leg {_key(leg)} {field}={leg[field]!r} but the "
                                   f"candidate row has {row[field]!r}")
        if not bool(row["eligible"]):
            raise RuntimeError(f"HALT: leg {_key(leg)} is not eligible: {row['ineligible_reasons']}")
        # N46: a ticket may be declared with up to `max_per_game` legs per game (the 20-leg
        # cannot be one per game on a 14-game Sunday). Extra legs in a game must be on
        # DIFFERENT TEAMS and a player appears once per ticket.
        teams = seen_events.setdefault(leg["event_id"], [])
        if len(teams) >= max_per_game:
            raise RuntimeError(f"HALT: {'two legs' if max_per_game == 1 else 'too many legs'} "
                               f"in one game: {leg['event_id']}")
        if row["team"] in teams:
            raise RuntimeError(f"HALT: two legs on one team ({row['team']}) in {leg['event_id']}")
        teams.append(row["team"])
        if (row["team"], leg["player_name"]) in seen_players:
            raise RuntimeError(f"HALT: {leg['player_name']} appears twice on one ticket")
        seen_players.add((row["team"], leg["player_name"]))


def log_ticket(log_path, entry, cand, max_per_game=1):
    """Append-only. An entry is never edited; (build_time, ticket_id) must be new; every leg is
    checked against the candidate table it came from."""
    log_path = Path(log_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    existing = json.loads(log_path.read_text()) if log_path.exists() and log_path.stat().st_size else []
    key = (entry["build_time"], entry["ticket_id"])
    if key in {(e["build_time"], e["ticket_id"]) for e in existing}:
        raise RuntimeError(f"HALT: {key} already logged — append-only")
    check_legs_against_candidates(entry["legs"], cand, max_per_game)
    merged = existing + [entry]
    log_path.write_text(json.dumps(merged, indent=2, default=str))
    return len(merged)


def log_final_ticket(log_path, cand, meta, final_keys, reasons, confirmations, reader,
                     top_k=TOP_K):
    """N44: the reader's ticket, built BY CODE from candidate rows and compared BY CODE with
    both baselines.

      final_keys     [(event_id, player_name, market_key), ...]  0..top_k legs; [] = no ticket
      reasons        {key: {"reason", "source"}} — REQUIRED for every baseline leg left out
                     and every final leg that is in neither baseline. Derived here, not
                     volunteered: a missing explanation halts.
      confirmations  {key: {"availability_source", "checked_at"}} — REQUIRED for every final
                     leg: the feed's status (or its absence) is not an inactive list.
      reader         {"model", "inputs", "raw_output"} — what was read and what was answered.
    """
    final_keys = [tuple(k) for k in final_keys]
    if len(final_keys) > top_k:
        raise RuntimeError(f"HALT: {len(final_keys)} legs > {top_k}")
    if len(set(final_keys)) != len(final_keys):
        raise RuntimeError("HALT: duplicate leg in the final ticket")
    for field in ("model", "inputs", "raw_output"):
        if not reader.get(field):
            raise RuntimeError(f"HALT: reader record missing {field}")
    legs = []
    for k in final_keys:
        m = cand[(cand["event_id"] == k[0]) & (cand["player_name"] == k[1]) & (cand["market_key"] == k[2])]
        if len(m) != 1:
            raise RuntimeError(f"HALT: {k} is not exactly one candidate row")
        legs.append(leg_record(m.iloc[0].to_dict()))
    check_legs_against_candidates(legs, cand)

    baselines = {"BASELINE_TOPK_Q": baseline_ticket(cand, top_k),
                 "BASELINE_ROLE_OVERS": role_overs_ticket(cand, top_k)}
    in_baseline = {_key(leg) for b in baselines.values() for leg in b}
    removed = sorted(in_baseline - set(final_keys))
    added = sorted(set(final_keys) - in_baseline)
    reasons = {tuple(k): v for k, v in reasons.items()}
    confirmations = {tuple(k): v for k, v in confirmations.items()}
    for k in removed + added:
        r = reasons.get(k) or {}
        if not r.get("reason") or not r.get("source"):
            raise RuntimeError(f"HALT: {'removed' if k in removed else 'added'} leg {k} "
                               "needs a reason AND a source")
    for k in final_keys:
        c = confirmations.get(k) or {}
        if not c.get("availability_source") or not c.get("checked_at"):
            raise RuntimeError(f"HALT: final leg {k} has no availability confirmation")
    entry = {
        "build_time": meta["build_time"], "ticket_id": "FINAL_READER", "kind": "reader_final",
        "manifest": meta, "legs": legs, "price": ticket_price(legs) if legs else None,
        "departures": {"removed_from_baselines": [list(k) for k in removed],
                       "added_outside_baselines": [list(k) for k in added]},
        "reasons": [{"leg": list(k), **v} for k, v in reasons.items()],
        "confirmations": [{"leg": list(k), **v} for k, v in confirmations.items()],
        "reader": reader, "placed": None, "graded": False,
    }
    return log_ticket(log_path, entry, cand), entry


def to_markdown(cand, meta, base):
    lines = [f"# NFL prop candidates — {meta['season']} week {meta['week']}", "",
             f"Build {meta['build_time']} | Hard Rock pull {meta['props_pull_timestamp']} "
             f"({meta['props_pull_age_hours']} h old) | {meta['events']} games, "
             f"{meta['props_rows']} rows | injuries {meta['injury_file']}", "",
             f"Eligible {int(cand['eligible'].sum())} of {len(cand)}. No edge is claimed: q is "
             "Hard Rock's own de-vigged probability.", "", "## Baseline ticket (rule only)", ""]
    for leg in base:
        lines.append(f"- {leg['player_name']} ({leg['team']}) {leg['market_key']} "
                     f"{leg['pick_side']} {leg['line']} @ {leg['pick_price']:+.0f}  q={leg['q_pick']:.3f}")
    lines += ["", f"Price: {ticket_price(base)}", "", "## Eligible legs by game", ""]
    lines.insert(lines.index("## Eligible legs by game"), "## Baseline 2 — lead-role Overs (rule only)")
    i = lines.index("## Eligible legs by game")
    for leg in role_overs_ticket(cand, len(base) or TOP_K):
        lines.insert(i, f"- {leg['player_name']} ({leg['team']}) {leg['market_key']} Over "
                        f"{leg['line']} @ {leg['pick_price']:+.0f}  q={leg['q_pick']:.3f}")
        i += 1
    lines.insert(i, "")
    e = cand[cand["eligible"]].sort_values(["commence_time", "home_team", "q_pick"],
                                           ascending=[True, True, False])
    for (kick, home, away), g in e.groupby(["commence_time", "home_team", "away_team"], sort=False):
        lines.append(f"### {away} @ {home} — {kick}")
        for r in g.to_dict("records"):
            share = r["carry_share"] if r["market_key"] == "player_rush_attempts" else r["target_share"]
            flag = " MOVED-AGAINST" if r.get("moved_against") is True else ""
            inj = f" [{r['injury_status']}]" if r.get("injury_status") else ""
            lines.append(f"- {r['player_name']} {r['market_key'].replace('player_', '')} "
                         f"{r['pick_side']} {r['line']} @ {r['pick_price']:+.0f} q={r['q_pick']:.3f} "
                         f"share={share:.3f}{inj}{flag}")
        lines.append("")
    return "\n".join(lines)


def log_final_from_file(final_path, season=2026):
    """The production entry for the reader's ticket: `--final reader_ticket.json`, holding
    candidates_file, final_keys, reasons, confirmations, reader. The candidate table is re-read
    from disk and its sha256 must equal the one the baselines were logged with."""
    spec = json.loads(Path(final_path).read_text())
    pq = ROOT / spec["candidates_file"]
    sha = hashlib.sha256(pq.read_bytes()).hexdigest()
    log_path = BOARD_DIR / f"nfl_prop_tickets_{season}.json"
    logged = [e for e in json.loads(log_path.read_text())
              if e["manifest"].get("candidates_file") == spec["candidates_file"]]
    if not logged or logged[0]["manifest"]["candidates_sha256"] != sha:
        raise RuntimeError(f"HALT: {spec['candidates_file']} has no logged baselines or its sha256 changed")
    cand = pd.read_parquet(pq)
    as_map = lambda items: {tuple(i["leg"]): {k: v for k, v in i.items() if k != "leg"} for i in items}  # noqa: E731
    return log_final_ticket(log_path, cand, logged[0]["manifest"], spec["final_keys"],
                            as_map(spec.get("reasons", [])), as_map(spec.get("confirmations", [])),
                            spec.get("reader", {}))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=2026)
    ap.add_argument("--build-time", help="ISO8601 UTC; default now")
    ap.add_argument("--top-k", type=int, default=TOP_K)
    ap.add_argument("--final", help="reader_ticket.json: log the reader's final ticket and exit")
    args = ap.parse_args()
    if args.final:
        n, entry = log_final_from_file(args.final, args.season)
        print(f"FINAL_READER logged ({len(entry['legs'])} legs, price {entry['price']}); log entries {n}")
        return
    bt = args.build_time or datetime.now(timezone.utc).isoformat()
    cand, meta = build_candidates(season=args.season, build_time=bt)
    base = baseline_ticket(cand, args.top_k)
    stamp = _utc(bt).strftime("%Y%m%dT%H%MZ")
    out_dir = BOARD_DIR / f"week={args.season}_{meta['week']:02d}"
    out_dir.mkdir(parents=True, exist_ok=True)
    pq = out_dir / f"nfl_prop_candidates_{stamp}.parquet"
    if pq.exists():
        raise RuntimeError(f"HALT: {pq} exists — refusing to overwrite")
    cand.to_parquet(pq, index=False)
    (out_dir / f"nfl_prop_candidates_{stamp}.md").write_text(to_markdown(cand, meta, base))
    meta["candidates_file"] = str(pq.relative_to(ROOT))
    meta["candidates_sha256"] = hashlib.sha256(pq.read_bytes()).hexdigest()
    log_path = BOARD_DIR / f"nfl_prop_tickets_{args.season}.json"
    overs = role_overs_ticket(cand, args.top_k)
    for ticket_id, legs in (("BASELINE_TOPK_Q", base), ("BASELINE_ROLE_OVERS", overs)):
        n = log_ticket(log_path, {
            "build_time": str(bt), "ticket_id": ticket_id, "kind": "baseline_rule",
            "manifest": meta, "legs": legs, "price": ticket_price(legs),
            "placed": None, "graded": False}, cand)
    print(json.dumps(meta, indent=2))
    print(f"eligible {int(cand['eligible'].sum())}/{len(cand)}; baseline {len(base)} legs; log entries {n}")
    if meta["props_pull_age_hours"] > MAX_PULL_AGE_HOURS:
        print(f"WARNING: newest pull is {meta['props_pull_age_hours']} h old — nothing is eligible")


if __name__ == "__main__":
    main()
