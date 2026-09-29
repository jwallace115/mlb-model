#!/usr/bin/env python3
"""Cowork 6E verification — real-side measurements (PBP 2021-24 REG, week <= 18, 1,087 games).

1. Live-play first downs by penalty (play_type pass/run, first_down_penalty == 1):
   rate per scrimmage play, yards_gained vs penalty_yards, ball advance to the next snap,
   time to the next row in normal vs late (last 2:00 of a half / last 5:00 of Q4) periods.
2. Team timeouts (timeout == 1 and timeout_team not null) by what the previous row was.

Run from the repo root: python3 research/nfl_sim/phase6e_cowork/real_live_pen_and_ns_timeouts.py
"""
import pandas as pd

COLS = ["game_id", "week", "play_id", "play_type", "qtr", "game_seconds_remaining",
        "half_seconds_remaining", "first_down_penalty", "penalty", "penalty_team", "posteam",
        "defteam", "yards_gained", "penalty_yards", "yardline_100", "down", "timeout",
        "timeout_team"]
p = pd.concat([pd.read_parquet(f"nfl/data/pbp/pbp_{s}.parquet", columns=COLS)
               for s in [2021, 2022, 2023, 2024]])
p = p[p.week <= 18].sort_values(["game_id", "play_id"]).reset_index(drop=True)
G = p.game_id.nunique()
g = p.groupby("game_id")
p["next_gsr"] = g.game_seconds_remaining.shift(-1)
p["next_yl"] = g.yardline_100.shift(-1)
p["next_pos"] = g.posteam.shift(-1)
p["prev_type"] = g.play_type.shift(1)
p["prev_to"] = g.timeout.shift(1)
p["prev_pen"] = g.penalty.shift(1)

print(f"games {G}")
# 1. live-play FD penalties
scr = p[p.play_type.isin(["pass", "run"])]
live = scr[scr.first_down_penalty == 1]
print(f"live FD pen {len(live)} / scrimmage {len(scr)} = {len(live)/len(scr):.5f}; per team {len(live)/G/2:.3f}")
print(f"  yards_gained mean {live.yards_gained.mean():.2f}; penalty_yards mean {live.penalty_yards.mean():.2f}; "
      f"sum {(live.yards_gained + live.penalty_yards).mean():.2f}")
adv = (live.yardline_100 - live.next_yl)[live.next_pos == live.posteam]
print(f"  advance to next snap: mean {adv.mean():.2f}, quantiles 10/25/50/75/90 "
      f"{adv.quantile([.1, .25, .5, .75, .9]).tolist()}")
el = live.game_seconds_remaining - live.next_gsr
late = (live.half_seconds_remaining <= 120) | ((live.qtr == 4) & (live.game_seconds_remaining <= 300))
print(f"  seconds to next row: normal mean {el[~late].mean():.1f} (median {el[~late].median():.0f}); "
      f"late mean {el[late].mean():.1f} (median {el[late].median():.0f}), n late {int(late.sum())}")

# 2. team timeouts by preceding row
to = (p.timeout == 1) & p.timeout_team.notna()
t = p[to]
print(f"team timeouts/game {to.sum()/G:.2f}")
def cls(r):
    if r.prev_type in ("pass", "run", "qb_kneel", "qb_spike"):
        return "after scrimmage play"
    if r.prev_type == "no_play":
        if r.prev_to == 1:
            return "after another timeout"
        if r.prev_pen == 1:
            return "after no-play penalty"
        return "after other no_play"
    if r.prev_type in ("punt", "field_goal", "kickoff", "extra_point"):
        return f"after {r.prev_type}"
    return "other (quarter start etc.)"
print((t.apply(cls, axis=1).value_counts() / G).round(3).to_string())
