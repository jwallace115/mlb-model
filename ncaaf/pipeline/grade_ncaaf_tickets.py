#!/usr/bin/env python3
"""
N04/N38: Grade NCAAF tickets — CLV from the last pre-kick snapshot.

WO11 rewrite:
  - Grades LEGS wherever they live (event tickets and card entries).
  - Skips pre_repair entries.
  - Close = last pre-kick row within 30 minutes of commence_time.
  - point_clv and prob_clv are separate, never blended.
  - Outcomes from CFBD (homePoints/awayPoints, completed).
  - UPDATE-ONLY: never append a row, never re-grade a row already marked graded.
"""

import json, sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

TAPE_DIR = ROOT / "data" / "odds_archive" / "ncaaf" / "line_history"
TICKET_LOG = ROOT / "ncaaf" / "logs" / "ncaaf_board_tickets_2026.json"

CLOSE_MAX_MINUTES = 30

# Odds API -> CFBD team name overrides (where strip-mascot doesn't work).
# N41: the prefix fallback can land on a DIFFERENT school — "Southern Mississippi Golden
# Eagles" shortens to "Southern" (Southern University). Every name that fails or mis-maps on
# the 2026 tape is listed here; the pair+date key in _compute_outcome is the second guard.
_TEAM_MAP = {
    "San Jose State Spartans": "San Jos\u00e9 State",
    "UMass Minutemen": "Massachusetts",
    "Southern Mississippi Golden Eagles": "Southern Miss",
    "Appalachian State Mountaineers": "App State",
    "Hawaii Rainbow Warriors": "Hawai'i",
    "Southeastern Louisiana Lions": "SE Louisiana",
}

# A tape commence_time can drift hours from CFBD's startDate (App State-Charlotte 2026-09-19:
# tape 01:32Z next day, CFBD 22:00Z). Same two teams within this window = same game.
OUTCOME_MATCH_HOURS = 36
FINAL_OUTCOMES = ("win", "loss", "push")
N12_MIN_LEGS = 10


def american_to_implied(odds):
    if odds is None or (isinstance(odds, float) and np.isnan(odds)):
        return np.nan
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def _odds_to_cfbd(odds_name, cfbd_teams):
    """Map an Odds API team name to a CFBD team name."""
    if odds_name in _TEAM_MAP:
        return _TEAM_MAP[odds_name]
    # Strip mascot: try progressively shorter prefixes
    words = odds_name.split()
    for i in range(len(words), 0, -1):
        candidate = " ".join(words[:i])
        if candidate in cfbd_teams:
            return candidate
    return None


def _load_tape(season):
    """Load all pre-kick snapshots with parsed timestamps."""
    tape_path = TAPE_DIR / f"season={season}"
    if not tape_path.exists():
        return pd.DataFrame()
    frames = []
    for f in sorted(tape_path.glob("*.parquet")):
        frames.append(pd.read_parquet(f))
    if not frames:
        return pd.DataFrame()
    df = pd.concat(frames, ignore_index=True)
    df["snapshot_dt"] = pd.to_datetime(df["snapshot_utc"], utc=True, errors="coerce")
    df["commence_dt"] = pd.to_datetime(df["commence_time"], utc=True, errors="coerce")
    # Pre-kick only
    return df[df["snapshot_dt"] < df["commence_dt"]].copy()


def _tape_kickoffs(tape):
    """event_id -> commence_time on the event's LAST pre-kick row.

    N41: the Odds API moves commence_time (127 of 189 events on the 2026 tape; median 6 min,
    max 640). App State-Charlotte 2026-09-19 was scheduled 22:00Z and kicked 01:32Z after
    delays; measured from the ticket's 22:00Z the "close" would be a quote 3.5 h before kick.
    """
    if tape.empty:
        return {}
    last = tape.sort_values("snapshot_dt").groupby("event_id")["commence_dt"].last()
    return last.to_dict()


def _load_cfbd_outcomes(season):
    """Load CFBD games. Returns ({frozenset(team_a, team_b): [game, ...]}, cfbd_teams).

    N41: keyed on the UNORDERED pair. CFBD and the Odds API disagree on home/away at neutral
    sites (Kansas-Arizona State, Virginia-West Virginia 2026-09-19), so an ordered key
    silently drops those games. Each game keeps its points BY TEAM NAME and its `completed`
    flag, so a scheduled-but-unplayed game reads as pending, not as missing.
    """
    cfbd_path = ROOT / "research" / "ncaaf" / f"cfbd_games_{season}.parquet"
    if not cfbd_path.exists():
        return {}, set()
    gdf = pd.read_parquet(cfbd_path)
    cfbd_teams = set(gdf["homeTeam"].unique()) | set(gdf["awayTeam"].unique())
    outcomes = {}
    for _, row in gdf.iterrows():
        start = pd.to_datetime(row["startDate"], utc=True, errors="coerce")
        if pd.isna(start):
            continue
        done = bool(row["completed"]) and pd.notna(row["homePoints"]) and pd.notna(row["awayPoints"])
        game = {
            "start": start,
            "completed": done,
            "points": {row["homeTeam"]: row["homePoints"], row["awayTeam"]: row["awayPoints"]},
        }
        outcomes.setdefault(frozenset((row["homeTeam"], row["awayTeam"])), []).append(game)
    return outcomes, cfbd_teams


def _find_close(tape, eid, book, market, side, commence_dt):
    """Find the last pre-kick row within 30 min of kickoff for this leg's book."""
    match = tape[
        (tape["event_id"] == eid)
        & (tape["market"] == market)
        & (tape["outcome_name"] == side)
        & (tape["bookmaker"] == book)
    ]
    if match.empty:
        return None, None

    # Filter to within 30 minutes of kickoff
    cutoff = commence_dt - pd.Timedelta(minutes=CLOSE_MAX_MINUTES)
    within = match[match["snapshot_dt"] >= cutoff]
    if within.empty:
        # Have data but too old — return as last_observed
        latest = match.sort_values("snapshot_dt", ascending=False).iloc[0]
        age_min = (commence_dt - latest["snapshot_dt"]).total_seconds() / 60
        return None, {"point": latest["point"], "price": latest["price"],
                      "snapshot_utc": str(latest["snapshot_utc"]),
                      "age_minutes": round(age_min, 1)}

    latest = within.sort_values("snapshot_dt", ascending=False).iloc[0]
    return latest, None


def _find_complement(tape, eid, book, market, side, snapshot_utc):
    """Find the complement side from the same book and snapshot."""
    comp = tape[
        (tape["event_id"] == eid)
        & (tape["market"] == market)
        & (tape["outcome_name"] != side)
        & (tape["bookmaker"] == book)
        & (tape["snapshot_utc"] == snapshot_utc)
    ]
    if comp.empty:
        return None
    return comp.iloc[0]


def _compute_outcome(leg, home_team, away_team, outcomes, cfbd_teams, commence_time=None):
    """Compute win/loss/push for a leg from CFBD outcomes.

    Returns (result, reason). result is one of FINAL_OUTCOMES, "pending" (game found, not
    completed in the CFBD file yet) or "outcome_unavailable" (no such game / unmapped team).
    Never a loss by default.
    """
    if not outcomes:
        return "outcome_unavailable", "no_cfbd_data"

    home_cfbd = _odds_to_cfbd(home_team, cfbd_teams)
    away_cfbd = _odds_to_cfbd(away_team, cfbd_teams)
    if not home_cfbd or not away_cfbd:
        return "outcome_unavailable", f"unmapped_teams:{home_team}/{away_team}"

    # N41: event tickets carry commence_time on the TICKET, cards on the leg. Reading only
    # the leg gave date '' -> no_match for every event-ticket leg.
    commence = leg.get("commence_time") or commence_time
    commence_dt = pd.to_datetime(commence, utc=True, errors="coerce") if commence else pd.NaT
    if pd.isna(commence_dt):
        return "outcome_unavailable", "no_commence_time"

    window = pd.Timedelta(hours=OUTCOME_MATCH_HOURS)
    games = [g for g in outcomes.get(frozenset((home_cfbd, away_cfbd)), [])
             if abs(g["start"] - commence_dt) <= window]
    if not games:
        return "outcome_unavailable", f"no_match:{home_cfbd}/{away_cfbd}/{str(commence_dt)[:10]}"
    if len(games) > 1:
        return "outcome_unavailable", f"ambiguous_match:{home_cfbd}/{away_cfbd}"
    game = games[0]
    if not game["completed"]:
        return "pending", "cfbd_not_completed"

    market = leg["market"]
    side = leg["side"]
    point = leg["point"]

    if market == "spreads":
        side_cfbd = _odds_to_cfbd(side, cfbd_teams)
        if side_cfbd not in game["points"]:
            return "outcome_unavailable", f"side_unmapped:{side}"
        other = home_cfbd if side_cfbd == away_cfbd else away_cfbd
        margin = game["points"][side_cfbd] - game["points"][other] + point
        if margin > 0:
            return "win", None
        if margin < 0:
            return "loss", None
        return "push", None

    if market == "totals":
        total = game["points"][home_cfbd] + game["points"][away_cfbd]
        if total == point:
            return "push", None
        over = "Over" in str(side)
        return ("win" if (total > point) == over else "loss"), None

    return "outcome_unavailable", f"unknown_market:{market}"


def grade_tickets(season=2026):
    """Grade ungraded tickets. Returns count of rows changed."""
    if not TICKET_LOG.exists():
        return 0

    with open(TICKET_LOG) as f:
        tickets = json.load(f)

    tape = _load_tape(season)
    if tape.empty:
        print("No tape data available")
        return 0

    outcomes, cfbd_teams = _load_cfbd_outcomes(season)
    now_utc = pd.Timestamp.now(tz="UTC")
    kickoffs = _tape_kickoffs(tape)

    changed = 0
    for ticket in tickets:
        if ticket.get("pre_repair"):
            continue
        if ticket.get("abstain"):
            continue  # N42: a logged abstain has no legs to grade
        if ticket.get("graded"):
            continue  # UPDATE-ONLY

        # Get commence_time from ticket or first leg
        ticket_commence = ticket.get("commence_time")
        if not ticket_commence:
            legs = ticket.get("legs", [])
            if legs:
                ticket_commence = legs[0].get("commence_time")
        if not ticket_commence:
            continue

        commence = pd.Timestamp(ticket_commence, tz="UTC")
        if commence > now_utc:
            continue

        all_legs_closeable = True
        all_outcomes_final = True
        for leg in ticket.get("legs", []):
            # Normalize: event_id and commence from leg or ticket
            eid = leg.get("event_id") or ticket.get("event_id")
            leg_commence = leg.get("commence_time") or ticket.get("commence_time")
            home = leg.get("home_team") or ticket.get("home_team", "")
            away = leg.get("away_team") or ticket.get("away_team", "")

            if not eid:
                leg["grade_status"] = "no_event_id"
                all_legs_closeable = False
                continue

            market = leg["market"]
            side = leg["side"]
            book = leg.get("book", "")
            # N41: the kickoff the books last quoted, not the one on the ticket (see
            # _tape_kickoffs). Falls back to the ticket's when the event is not on the tape.
            commence_dt = kickoffs.get(eid, pd.Timestamp(leg_commence, tz="UTC"))
            leg["kickoff_used_utc"] = commence_dt.isoformat()

            # N41: a card's later games may not have kicked when its first one has. Taking a
            # "close" for them now would freeze a pre-close quote as the close.
            if commence_dt > now_utc:
                leg["grade_status"] = "not_started"
                all_legs_closeable = False
                all_outcomes_final = False
                continue
            leg.pop("grade_status", None)

            if not book:
                leg["grade_status"] = "no_book"
                all_legs_closeable = False
                continue

            # Outcome from CFBD — N41: BEFORE the close lookup. The result of a game does
            # not depend on whether a close was captured; it used to be skipped with it.
            result, reason = _compute_outcome(leg, home, away, outcomes, cfbd_teams,
                                              commence_time=leg_commence)
            leg["outcome"] = result
            if reason:
                leg["outcome_reason"] = reason
            else:
                leg.pop("outcome_reason", None)
            if result not in FINAL_OUTCOMES:
                all_outcomes_final = False

            # Find close within 30 minutes
            close_row, last_obs = _find_close(tape, eid, book, market, side, commence_dt)

            if close_row is None:
                if last_obs:
                    leg["last_observed_point"] = float(last_obs["point"]) if pd.notna(last_obs["point"]) else None
                    leg["last_observed_price"] = float(last_obs["price"]) if pd.notna(last_obs["price"]) else None
                    leg["last_observed_age_min"] = last_obs["age_minutes"]
                leg["point_clv"] = None
                leg["prob_clv"] = None
                all_legs_closeable = False
                continue

            close_point = float(close_row["point"]) if pd.notna(close_row["point"]) else None
            close_price = float(close_row["price"]) if pd.notna(close_row["price"]) else None
            leg["close_point"] = close_point
            leg["close_price"] = close_price
            leg["close_book"] = str(close_row["bookmaker"])
            leg["close_snapshot_utc"] = str(close_row["snapshot_utc"])

            entry_point = leg.get("point")

            # point_clv
            if close_point is not None and entry_point is not None:
                if market == "spreads":
                    leg["point_clv"] = round(entry_point - close_point, 2)
                elif "Over" in str(side):
                    leg["point_clv"] = round(close_point - entry_point, 2)
                else:  # Under
                    leg["point_clv"] = round(entry_point - close_point, 2)
            else:
                leg["point_clv"] = None

            # prob_clv: only if close quotes the ORIGINAL point at this book
            leg["prob_clv"] = None
            leg["prob_clv_reason"] = None
            if close_point is not None and entry_point is not None and close_point == entry_point:
                # Find close complement
                close_comp = _find_complement(
                    tape, eid, book, market, side,
                    close_row["snapshot_utc"])
                if close_comp is not None:
                    q_c = american_to_implied(close_price)
                    comp_c = american_to_implied(float(close_comp["price"]))
                    if pd.notna(q_c) and pd.notna(comp_c) and (q_c + comp_c) > 0:
                        q_c_devig = q_c / (q_c + comp_c)

                        # Entry de-vig uses the ENTRY complement
                        entry_price = leg.get("price")
                        comp_entry_price = leg.get("complement_price")
                        if entry_price is not None and comp_entry_price is not None:
                            q_0 = american_to_implied(entry_price)
                            comp_0 = american_to_implied(comp_entry_price)
                            if pd.notna(q_0) and pd.notna(comp_0) and (q_0 + comp_0) > 0:
                                q_0_devig = q_0 / (q_0 + comp_0)
                                d_0 = 1.0 / q_0_devig if q_0_devig > 0 else None
                                if d_0 is not None:
                                    leg["prob_clv"] = round(q_c_devig - q_0_devig, 6)
                                    leg["prob_clv_C"] = round(d_0 * q_c_devig - 1, 6)
                                    leg["prob_clv_reason"] = None
                            else:
                                leg["prob_clv_reason"] = "entry_complement_missing"
                        else:
                            leg["prob_clv_reason"] = "entry_complement_missing"
                    else:
                        leg["prob_clv_reason"] = "close_complement_invalid"
                else:
                    leg["prob_clv_reason"] = "close_complement_missing"
            elif close_point != entry_point:
                leg["prob_clv_reason"] = "line_moved_no_alt_quote"

        # N41: `graded` is terminal (UPDATE-ONLY skips it for ever), so it needs every leg's
        # close AND a final result. A game CFBD has not completed yet stays ungraded and is
        # picked up on a later run.
        if all_legs_closeable and all_outcomes_final:
            ticket["graded"] = True
            ticket.pop("grade_status", None)
            changed += 1
        elif not all_legs_closeable:
            ticket["grade_status"] = "close_unavailable"
        else:
            ticket["grade_status"] = "outcome_pending"

    # N12: assert that not all CLVs are exactly zero
    if changed > 0:
        all_clvs = []
        for t in tickets:
            if t.get("graded") and not t.get("pre_repair"):
                for leg in t.get("legs", []):
                    v = leg.get("point_clv")
                    if v is not None:
                        all_clvs.append(v)
        # N41: only with enough legs to mean something. With one graded leg whose line did
        # not move (about half of them), the old check halted the grader and wrote nothing.
        if len(all_clvs) >= N12_MIN_LEGS and all(c == 0.0 for c in all_clvs):
            raise RuntimeError(
                f"HALT: all {len(all_clvs)} graded point_clvs are exactly 0.0. "
                f"Likely a future-game grading defect.")

    with open(TICKET_LOG, "w") as f:
        json.dump(tickets, f, indent=2)

    return changed


def report(season=2026):
    """Print CLV breakdown."""
    if not TICKET_LOG.exists():
        return

    with open(TICKET_LOG) as f:
        tickets = json.load(f)

    graded = [t for t in tickets if t.get("graded") and not t.get("pre_repair")]
    if not graded:
        print("No graded tickets (excluding pre_repair)")
        return

    legs = []
    for t in graded:
        for leg in t.get("legs", []):
            leg["_event_id"] = leg.get("event_id") or t.get("event_id", "")
            leg["_home"] = leg.get("home_team") or t.get("home_team", "")
            leg["_away"] = leg.get("away_team") or t.get("away_team", "")
            leg["_reference_only"] = t.get("reference_only", True)
            legs.append(leg)

    df = pd.DataFrame(legs)

    # point_clv report
    has_pt = df[df["point_clv"].notna()] if "point_clv" in df.columns else pd.DataFrame()
    print(f"\nPoint CLV: {len(has_pt)}/{len(df)} legs")
    if not has_pt.empty:
        print("\n| Market | N | Mean pt_CLV |")
        print("|--------|---|-------------|")
        for mkt in sorted(has_pt["market"].unique()):
            g = has_pt[has_pt["market"] == mkt]
            print(f"| {mkt:10s} | {len(g):3d} | {g['point_clv'].mean():+.2f} |")
        print(f"\nOverall: {has_pt['point_clv'].mean():+.2f} (N={len(has_pt)})")

    # Outcome report
    if "outcome" in df.columns:
        print(f"\nOutcomes:")
        for o in ["win", "loss", "push", "outcome_unavailable"]:
            n = (df["outcome"] == o).sum()
            if n > 0:
                print(f"  {o}: {n}")

    match_rate = (df["outcome"].isin(["win", "loss", "push"])).sum() if "outcome" in df.columns else 0
    print(f"\nCFBD match rate: {match_rate}/{len(df)} legs")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args()

    if not args.report_only:
        changed = grade_tickets(args.season)
        print(f"Graded: {changed} tickets changed")

    report(args.season)


if __name__ == "__main__":
    main()
