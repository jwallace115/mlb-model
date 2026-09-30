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

# VM props slots (UTC hours), from WO12 deploy
VM_SLOTS = [2, 14, 15, 16, 22, 23.75]  # 23:45 = MNF slot

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
        for h in sorted(VM_SLOTS, reverse=True):
            slot = datetime(day.year, day.month, day.day,
                            int(h), int((h % 1) * 60), tzinfo=timezone.utc)
            if slot < dt_utc:
                if best is None or slot > best:
                    best = slot
                return best
    return best


def group_windows(games_df):
    """Group games into kick windows (TNF, London, Sunday main+SNF, MNF)."""
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
        elif (g["kick_utc"] - current[-1]["kick_utc"]).total_seconds() <= 5 * 3600:
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


def main():
    sched = load_schedule([4, 5])
    lines = []

    lines.append("# FWD1 Runbook — NFL sim v1 forward test, weeks 4-5")
    lines.append("")
    lines.append(f"Reader model: `{READER_MODEL}`")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}")
    lines.append("")
    lines.append("## Measured runtimes (D231)")
    lines.append(f"- Sim: ~{SECS_PER_GAME}s per game")
    lines.append(f"- Input refresh: ~{REFRESH_MIN} min (pull_nflverse 6s + ratings.py ~8min)")
    lines.append(f"- IMPORTANT: ratings.py overwrites params_v1.json — always `git checkout nfl/sim/params_v1.json` after")
    lines.append("")
    lines.append("## Input refresh (ONCE per week, Wednesday)")
    lines.append("```bash")
    lines.append("cd ~/mlb-model")
    lines.append("python3 nfl/sim/pull_nflverse_inputs.py")
    lines.append("python3 nfl/sim/ratings.py")
    lines.append("git checkout nfl/sim/params_v1.json")
    lines.append("python3 -m pytest nfl/sim/tests/test_freeze_v1.py -q  # must pass")
    lines.append("```")

    for week in [4, 5]:
        wk = sched[sched["week"] == week]
        if wk.empty:
            continue
        lines.append("")
        lines.append(f"## Week {week}")
        windows = group_windows(wk)

        for win_games in windows:
            first_kick = min(g["kick_utc"] for g in win_games)
            last_kick = max(g["kick_utc"] for g in win_games)
            n_games = len(win_games)

            # Window hours: covers first to last kick + 1h
            window_h = max(2.0, (last_kick - first_kick).total_seconds() / 3600 + 1.0)
            window_h = round(window_h * 2) / 2  # round to 0.5

            # Runtime
            sim_min = n_games * SECS_PER_GAME / 60
            total_min = sim_min + REFRESH_MIN + MARGIN_MIN
            latest_start = first_kick - timedelta(minutes=total_min)

            # Nearest VM slot
            vm_slot = latest_vm_slot_before(latest_start)
            if vm_slot:
                slot_age_h = (latest_start - vm_slot).total_seconds() / 3600
            else:
                slot_age_h = 99

            game_list = ", ".join(f"{g['away']}@{g['home']}" for g in win_games)

            lines.append("")
            lines.append(f"### {window_label(win_games)}")
            lines.append(f"Games: {game_list}")
            lines.append("")
            lines.append("```bash")
            lines.append(f"python3 nfl/sim/run_forward_v1.py --week {week} --window-hours {window_h}")
            lines.append("```")
            lines.append("")
            lines.append(f"Latest safe start: **{format_utc(latest_start)}** ({format_et(latest_start)})")
            lines.append(f"Runtime: {n_games} games × {SECS_PER_GAME}s = {sim_min:.0f} min + {REFRESH_MIN} min refresh + {MARGIN_MIN} min margin")
            if vm_slot:
                lines.append(f"VM props slot: {vm_slot.strftime('%H:%MZ %a')} (~{slot_age_h:.1f}h old at run time)")
            if slot_age_h > QUOTE_MAX_AGE_H:
                lines.append(f"**STALE**: VM slot is {slot_age_h:.1f}h old (> {QUOTE_MAX_AGE_H}h). Manual pull required:")
                lines.append("```bash")
                lines.append(f"python3 nfl/pipeline/pull_hardrock_props.py --window-hours 2 --tag close \\")
                lines.append(f"  --out-dir data/odds_archive/nfl/props/season=2026/manual")
                lines.append("```")
                lines.append("Credit cost: ~10 per event × 1 region = 10 credits")

    lines.append("")
    lines.append("## Scoring")
    lines.append("")
    lines.append("```bash")
    lines.append("python3 nfl/pipeline/log_ai_opinions.py score-experiment --experiment nfl_fwd_v1")
    lines.append("```")
    lines.append("")
    lines.append("## Notes")
    lines.append("")
    lines.append("- **Anchor rule (D210):** game whose anchored mean misses market by > 1.0 pt = unanchored, reported separately.")
    lines.append("- **Game lines (h2h, spreads, totals):** always no_view (sim is market-anchored).")
    lines.append("- **Pilot files:** never pooled; only with `--include-pilot`.")
    lines.append("- **500 legs = descriptive; 1,500 legs = confirmatory.**")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
