#!/usr/bin/env python3
"""D235: generate the FWD1 runbook from the nflverse schedule and the line tape.

Usage: python3 research/nfl_sim/make_runbook.py > research/nfl_sim/fwd1_runbook.md
"""
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

READER_MODEL = "nfl_sim_v1_156cd057"
SECS_PER_GAME = 30  # measured D231
MARGIN_MIN = 3  # minutes margin
REFRESH_MIN = 9  # pull_nflverse 6s + ratings.py ~8min = ~9min
QUOTE_MAX_AGE_H = 3.0

# VM props slots (UTC hours) by weekday (Mon=0), from the WO12 deploy: Tue-Sat 02:00 and
# 14:00, Thu 22:00 (TNF), Sun 15:00 and 16:00, Mon 23:45 only (after an MNF 23:30 start).
# D272: slots are per weekday — the old flat list invented a Monday 22:00 pull.
VM_SLOTS_BY_DOW = {0: [23.75], 1: [2, 14], 2: [2, 14], 3: [2, 14, 22], 4: [2, 14],
                   5: [2, 14], 6: [15, 16]}

ET_OFFSET = timedelta(hours=-4)  # EDT


def load_schedule(weeks):
    import nflreadpy
    sched = nflreadpy.load_schedules([2026])
    if hasattr(sched, "to_pandas"):
        sched = sched.to_pandas()
    return sched[sched["week"].isin(weeks)]


def game_kick_utc(row):
    """Parse gameday + gametime (ET) to UTC."""
    et_str = f"{row['gameday']}T{row['gametime']}:00-04:00"
    return datetime.fromisoformat(et_str).astimezone(timezone.utc)


def format_utc(dt):
    return dt.strftime("%a %Y-%m-%d %H:%MZ")


def format_et(dt):
    et = dt + ET_OFFSET
    return et.strftime("%a %-I:%M %p ET")


def latest_vm_slot_before(dt_utc):
    """Find the latest VM props slot strictly before dt_utc on the same or previous day."""
    best = None
    for days_back in range(3):
        day = (dt_utc - timedelta(days=days_back)).date()
        for h in sorted(VM_SLOTS_BY_DOW[day.weekday()], reverse=True):
            slot = datetime(day.year, day.month, day.day,
                            int(h), int((h % 1) * 60), tzinfo=timezone.utc)
            if slot < dt_utc:
                if best is None or slot > best:
                    best = slot
                return best
    return best


MAIN_PULL_UTC_MIN = 16 * 60 + 30   # D272: Sunday games kicking before 16:30Z precede the
                                   # VM's 16:00Z props pull and get their own window


def _early_sunday(kick):
    return kick.weekday() == 6 and kick.hour * 60 + kick.minute < MAIN_PULL_UTC_MIN


def group_windows(games_df):
    """Group games into kick windows (TNF, early Sunday/international, Sunday main+SNF, MNF).
    D272 (audit #14 A3): a chain of games within 5 h of each other is ONE window, except
    that a Sunday game kicking before 16:30Z never shares a window with a later game —
    its quotes must come from a manual morning pull, not the 16:00Z VM pull."""
    games = []
    for _, r in games_df.iterrows():
        kick = game_kick_utc(r)
        games.append({"game_id": r["game_id"], "away": r["away_team"],
                       "home": r["home_team"], "kick_utc": kick})
    games.sort(key=lambda g: g["kick_utc"])

    windows = []
    current = []
    for g in games:
        if not current:
            current.append(g)
        elif ((g["kick_utc"] - current[-1]["kick_utc"]).total_seconds() <= 5 * 3600
              and _early_sunday(current[-1]["kick_utc"]) == _early_sunday(g["kick_utc"])):
            current.append(g)
        else:
            windows.append(current)
            current = [g]
    if current:
        windows.append(current)
    return windows


def window_label(games):
    kicks = sorted(set(g["kick_utc"] for g in games))
    first = kicks[0]
    dow = first.strftime("%a")
    if len(games) == 1:
        g = games[0]
        return f"{g['away']}@{g['home']} — {format_utc(first)} ({format_et(first)})"
    if dow == "Thu" or (first.weekday() == 3 and first.hour >= 20):
        label = "TNF"
    elif first.hour < 12 and first.weekday() in (5, 6):
        label = "London"
    elif first.weekday() == 0 and first.hour >= 20:
        label = "MNF"
    elif len(games) >= 3:
        label = f"Sunday main + SNF ({len(games)} games)"
    else:
        label = f"{len(games)} games"
    times = ", ".join(k.strftime("%H:%MZ") for k in kicks)
    return f"{label} — {format_utc(first).split()[0]} {first.strftime('%Y-%m-%d')} [{times}] ({format_et(first)}+)"


HARNESS = "python3 -I -S -B nfl/sim/fwd_bootstrap.py harness"


def main():
    weeks = [int(w) for w in (sys.argv[1:] or ["4", "5"])]
    sched = load_schedule(weeks)
    L = []
    L.append(f"# Forward-run runbook — nfl_fwd_v1, weeks {', '.join(map(str, weeks))} (D272)")
    L.append("")
    L.append(f"Reader model: `{READER_MODEL}`. Generated {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')} "
             "by `research/nfl_sim/make_runbook.py`. Run every command from the checkout that holds the refreshed "
             "inputs. Every forward run goes through the bootstrap (D266).")
    L.append("")
    L.append("## Input refresh (D271/D272) — per window, never at the last minute")
    L.append("")
    L.append("```bash")
    L.append("python3 nfl/sim/refresh_inputs.py --week W")
    L.append("```")
    L.append("")
    L.append("- About 10 min (ratings.py about 8). Exit 0: every team playing week W passes the forward gate. "
             "Exit 1: the refreshed tables ARE installed but the named teams are not ready (usually an "
             "unpublished injury report); a run including them HALTs. Exception: refresh failed, old tables restored.")
    L.append("- Sunday/Monday: after the final injury reports (Friday afternoon ET), and again on game morning, "
             "finishing at least 30 min before the window's harness start.")
    L.append("- TNF: after Wednesday's report, and again Thursday afternoon.")
    L.append("- Never re-pull 2020-2025 PBP; never install or upgrade Python packages (D269/D270).")
    L.append("")
    L.append("## Roster information cutoff (declared, D272)")
    L.append("")
    L.append("Each window freezes on the rosters and injury report of its LAST refresh before the harness "
             "start. Game-day inactives announced after that refresh (about 90 min before each kick) are NOT "
             "in the live active universe. The backtest used final game-day rosters, so live and "
             "backtest rosters are not identical for late games. This is a declared input difference, not "
             "final-roster parity. Out/Doubtful from the final injury report ARE applied.")
    for week in weeks:
        wk = sched[(sched["week"] == week) & (sched.get("game_type", "REG") == "REG")]
        if wk.empty:
            continue
        L.append("")
        L.append(f"## Week {week}")
        for win in group_windows(wk):
            first = min(g["kick_utc"] for g in win)
            last = max(g["kick_utc"] for g in win)
            if first.weekday() == 6 and not _early_sunday(first):
                start = first.replace(hour=16, minute=15)
                pull = "the VM's Sunday 16:00Z props pull (confirm it arrived)"
            else:
                start = first - timedelta(minutes=45)
                slot = latest_vm_slot_before(start)
                age = (start - slot).total_seconds() / 3600 if slot else 99
                pull = (f"the VM's {slot.strftime('%a %H:%MZ')} props pull ({age:.1f} h old at start)"
                        if age <= QUOTE_MAX_AGE_H - 0.5 else
                        f"a MANUAL props pull at {format_utc(first - timedelta(minutes=75))}")
            # --window-hours counts from the harness start: last kick + 30 min, up to the half hour
            import math
            hours = math.ceil(((last - start).total_seconds() / 3600 + 0.5) * 2) / 2
            games = ", ".join(f"{g['away']}@{g['home']}" for g in win)
            L.append("")
            L.append(f"### {window_label(win)}")
            L.append(f"Games ({len(win)}): {games}")
            L.append(f"- Quotes: {pull}; game lines from the 30-min tape. Max quote age 3 h at the harness start.")
            if "MANUAL" in pull:
                L.append("```bash")
                L.append("python3 nfl/pipeline/pull_hardrock_props.py --window-hours 2 --tag close \\")
                L.append("  --out-dir data/odds_archive/nfl/props/season=2026/manual")
                L.append("```")
            L.append(f"- Harness start: **{format_utc(start)}** ({format_et(start)}); sim about "
                     f"{len(win) * SECS_PER_GAME / 60:.0f} min.")
            L.append("```bash")
            L.append(f"{HARNESS} --week {week} --window-hours {hours:g}")
            L.append("```")
    L.append("")
    L.append("## Notes")
    L.append("")
    L.append("- A freshness or quote-age HALT is the gate working: do not override it for a primary. "
             "`--allow-stale-quotes` is pilot/dry-run only.")
    L.append("- Game lines (h2h, spreads, totals) are always no_view (the sim is market-anchored).")
    L.append("- Pilot files are never pooled; scoring follows the pre-registered rules (D269 L5, D270).")
    print("\n".join(L))


if __name__ == "__main__":
    main()
