#!/usr/bin/env python3
"""Quick test: verify location-split team states are computed correctly."""
import sys
sys.path.insert(0, "/root/mlb-model")
from nba.run_nba import _build_current_team_states

states = _build_current_team_states("2026-04-11")
for team in ["BOS", "LAL", "GSW"]:
    if team in states:
        s = states[team]
        oh = s.get("ortg_home", "MISSING")
        oa = s.get("ortg_away", "MISSING")
        dh = s.get("drtg_home", "MISSING")
        da = s.get("drtg_away", "MISSING")
        ph = s.get("pace_home", "MISSING")
        pa = s.get("pace_away", "MISSING")
        diff_o = round(abs(float(oh) - float(oa)), 1) if oh != "MISSING" and oa != "MISSING" else "N/A"
        print(f"{team}:")
        print(f"  ortg={s['ortg']} ortg_home={oh} ortg_away={oa} (delta={diff_o})")
        print(f"  drtg={s['drtg']} drtg_home={dh} drtg_away={da}")
        print(f"  pace={s['pace']} pace_home={ph} pace_away={pa}")

# Verify all 30 teams have location keys
missing = []
for t, s in states.items():
    for k in ["ortg_home", "ortg_away", "drtg_home", "drtg_away", "pace_home", "pace_away"]:
        if k not in s:
            missing.append((t, k))

print(f"\nTotal teams: {len(states)}")
print(f"Missing location keys: {len(missing)}")
if missing:
    for t, k in missing[:5]:
        print(f"  {t} missing {k}")
else:
    print("All teams have location-split keys -- PASS")
