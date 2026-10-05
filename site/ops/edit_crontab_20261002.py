#!/usr/bin/env python3
"""Apply the 2026-10-02 pipeline-audit changes to the VM crontab text (stdin -> stdout).
Every change is listed on stderr. Lines are commented out, never deleted. Idempotent."""
import re
import sys

TAG = "# DISABLED 2026-10-02 (pipeline audit): "
DISABLE = [
    ("nba/run_nba.py", "stats.nba.com blocks the VM (403); NBA runs on the Mac"),
    ("shared/closing_line_runner.py", "no pending plays since the V1 retirement; captures 0 every run"),
    ("mlb_sim/pipeline/mlb_scratch_checker.py", "serves retired V1 signals; no-op every run"),
    ("wnba/pipeline/build_features.py", "WNBA off-season"),
    ("wnba/pipeline/run_model.py", "WNBA off-season"),
    ("wnba_archetype_board/pipeline/assign_archetypes.py", "WNBA off-season (System A has no write step)"),
    ("wnba/pipeline/pull_live_games.py", "stub: prints 'would execute here'"),
    ("wnba/pipeline/push_signals.py", "WNBA off-season"),
]
out, changes = [], []
lines = sys.stdin.read().splitlines()
for line in lines:
    s = line.strip()
    if not s or s.startswith("#") or re.match(r"^[A-Z_]+=", s):
        out.append(line)
        continue
    hit = next((why for key, why in DISABLE if key in line), None)
    if hit:
        out.append(TAG + hit)
        out.append("# " + line)
        changes.append("disabled: " + line[:110])
        continue
    if "golf_daily_runner.py --capture grade" in line:
        new = line.replace("python3 golf/shadow/golf_daily_runner.py --capture grade",
                           "python3 golf/shadow/golf_grader.py --include-matchups")
        out.append("# FIXED 2026-10-02: '--capture grade' is not a mode of golf_daily_runner.py; the grader is golf_grader.py")
        out.append(new)
        changes.append("golf grader: " + new[:110])
        continue
    if "multi_book_open_capture.py --sports americanfootball_nfl" in line and "basketball_nba" not in line:
        new = line.replace("icehockey_nhl >>", "icehockey_nhl basketball_nba >>")
        if new == line:
            raise SystemExit("tape line did not have the expected form: " + line)
        out.append("# 2026-10-02: NBA added to the 30-min tape ahead of Oct 20 (+3 credits/call)")
        out.append(new)
        changes.append("tape: + basketball_nba")
        continue
    if "pull_team_totals.py && python3 mlb/pipeline/team_total_signal.py >>" in line:
        new = line.replace("python3 mlb/pipeline/pull_team_totals.py && python3 mlb/pipeline/team_total_signal.py >>",
                           "(python3 mlb/pipeline/pull_team_totals.py && python3 mlb/pipeline/team_total_signal.py) >>")
        out.append(new)
        changes.append("team totals: both commands now logged")
        continue
    out.append(line)

block = [
    "",
    "# ── Pipeline health + website (pipeline audit 2026-10-02) ──",
    "2-59/15 * * * * cd /root/mlb-model && /root/mlb-model/venv/bin/python3 shared/pipeline/pipeline_health.py >> /root/logs/pipeline_health.log 2>&1",
    "4-59/5 * * * * cd /root/mlb-model && /root/mlb-model/venv/bin/python3 site/build_site.py --out /var/www/iamnotuncertain >> /root/logs/site_build.log 2>&1",
    "# History spender: spends credits above the month's reserve on the historical archive (shared/pipeline/history_jobs.json), 06:10-13:00 UTC",
    "10 6 * * * cd /root/mlb-model && /root/mlb-model/venv/bin/python3 shared/pipeline/history_spender.py --until 13:00 >> /root/logs/history_spender.log 2>&1",
]
if not any("pipeline_health.py" in l for l in lines):
    out.extend(block)
    changes.append("added: pipeline_health every 15 min (:02), site build every 5 min (:04), history spender 06:10 daily")
sys.stdout.write("\n".join(out) + "\n")
for c in changes:
    print(c, file=sys.stderr)
