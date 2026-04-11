#!/usr/bin/env python3
"""NBA Archetype Revalidation - Honest OOS evaluation of frozen team sets."""

import pandas as pd
import numpy as np
from pathlib import Path
import os

OUT = Path("/root/mlb-model/research/recovery/nba_archetype_revalidation")

ARCHETYPES = {
    "ELITE_DEF2_at_ELITE_DEF": {
        "description": "ELITE_DEF2 @ ELITE_DEF -> UNDER signal",
        "direction": "UNDER",
        "away_set": {"HOU", "LAC", "LAL", "MIA", "NYK", "ORL", "SAC"},
        "home_set": {"BOS", "CLE", "GSW", "MIL", "MIN", "OKC"},
        "match_fn": "away_in_A_home_in_B",
    },
    "BALANCED_OFF_vs_PASSIVE_DEF": {
        "description": "BALANCED_OFF vs PASSIVE_DEF -> OVER signal (shot profile)",
        "direction": "OVER",
        "set_A": {"DEN", "HOU", "IND", "NYK", "OKC"},
        "set_B": {"BOS", "CHI", "CLE", "DEN", "LAL", "MIA", "MIL", "NYK", "PHX", "SAS", "UTA", "WAS"},
        "match_fn": "either_direction",
    },
    "ROAD_WARRIOR_at_STRONG_HOME": {
        "description": "ROAD_WARRIOR @ STRONG_HOME -> OVER signal (venue)",
        "direction": "OVER",
        "away_set": {"ATL", "CHI", "DAL", "DET", "GSW", "HOU", "NYK", "PHI", "PHX", "UTA"},
        "home_set": {"ATL", "BOS", "DEN", "IND", "MIL", "OKC", "POR", "SAS"},
        "match_fn": "away_in_A_home_in_B",
    },
    "ELITE_OREB_vs_WEAK_BOXOUT": {
        "description": "ELITE_OREB vs WEAK_BOXOUT -> OVER modifier",
        "direction": "OVER",
        "set_A": {"ATL", "BOS", "CLE", "DEN", "DET", "GSW", "HOU",
                  "MEM", "NOP", "NYK", "ORL", "POR", "SAC", "TOR", "UTA"},
        "set_B": {"CHA", "DAL", "DEN", "MEM", "MIN", "NOP", "NYK",
                  "OKC", "PHI", "PHX", "POR", "SAS", "TOR", "UTA", "WAS"},
        "match_fn": "either_direction",
    },
}


def match_game(arch, home, away):
    fn = arch["match_fn"]
    if fn == "away_in_A_home_in_B":
        return away in arch["away_set"] and home in arch["home_set"]
    elif fn == "either_direction":
        A, B = arch["set_A"], arch["set_B"]
        return (away in A and home in B) or (home in A and away in B)
    return False


# Load data
feat = pd.read_parquet("/root/mlb-model/nba/data/features.parquet")
feat["date"] = pd.to_datetime(feat["date"])
closing = pd.read_parquet("/root/mlb-model/nba/data/nba_historical_closing_lines.parquet")
closing["date"] = pd.to_datetime(closing["date"])

df = feat.merge(closing[["game_id", "close_total", "opening_total"]], on="game_id", how="left")
print("Games loaded:", len(df))
print("With closing lines:", df["close_total"].notna().sum())
print("Seasons:", sorted(df["season"].unique()))
print()

TRUE_OOS_SEASONS = ["2022-23", "2023-24"]
INSAMPLE_SEASONS = ["2024-25"]

# ── PHASE 1 ─────────────────────────────────────────────────────────
p1 = ["# Phase 1: Locked Archetype Identities", ""]
for name, arch in ARCHETYPES.items():
    p1.append("## " + name)
    p1.append("Direction: " + arch["direction"])
    p1.append("Description: " + arch["description"])
    if arch["match_fn"] == "away_in_A_home_in_B":
        p1.append("Away set: " + str(sorted(arch["away_set"])))
        p1.append("Home set: " + str(sorted(arch["home_set"])))
    else:
        p1.append("Set A: " + str(sorted(arch["set_A"])))
        p1.append("Set B: " + str(sorted(arch["set_B"])))
    p1.append("")
(OUT / "phase1_identities.md").write_text("\n".join(p1))

# ── PHASE 2-3 ───────────────────────────────────────────────────────
results_all = []
p23 = ["# Phase 2-3: Historical Application & OOS Split", ""]

for arch_name, arch in ARCHETYPES.items():
    direction = arch["direction"]
    p23.append("## " + arch_name + " (" + direction + ")")
    p23.append("")

    mask = df.apply(lambda r: match_game(arch, r["home_team"], r["away_team"]), axis=1)
    matched = df[mask].copy()
    p23.append("Total matched games: " + str(len(matched)))
    p23.append("")

    for window_name, seasons in [("TRUE_OOS (2022-24)", TRUE_OOS_SEASONS),
                                 ("IN_SAMPLE (2024-25)", INSAMPLE_SEASONS)]:
        sub = matched[matched["season"].isin(seasons)].copy()
        if len(sub) == 0:
            p23.append("### " + window_name + ": 0 games")
            p23.append("")
            continue

        has_line = sub["close_total"].notna()
        sub_line = sub[has_line].copy()

        if direction == "UNDER":
            sub_line["hit"] = sub_line["actual_total"] < sub_line["close_total"]
            sub_line["push"] = sub_line["actual_total"] == sub_line["close_total"]
        else:
            sub_line["hit"] = sub_line["actual_total"] > sub_line["close_total"]
            sub_line["push"] = sub_line["actual_total"] == sub_line["close_total"]

        n = len(sub_line)
        non_push = sub_line[~sub_line["push"]]
        hits = int(non_push["hit"].sum())
        misses = len(non_push) - hits
        pushes = int(sub_line["push"].sum())
        hit_rate = hits / len(non_push) if len(non_push) > 0 else 0

        roi_units = hits * (100 / 110) - misses * 1.0
        roi_pct = roi_units / len(non_push) * 100 if len(non_push) > 0 else 0

        if direction == "UNDER":
            edge_pts = (sub_line["close_total"] - sub_line["actual_total"]).mean()
        else:
            edge_pts = (sub_line["actual_total"] - sub_line["close_total"]).mean()

        p23.append("### " + window_name)
        p23.append("- Games with lines: %d (pushes: %d)" % (n, pushes))
        p23.append("- Record: %d-%d (%.1f%%)" % (hits, misses, hit_rate * 100))
        p23.append("- ROI @ -110: %+.1f%%" % roi_pct)
        p23.append("- Directional edge: %+.1f pts" % edge_pts)
        p23.append("")

        for ssn in sorted(sub_line["season"].unique()):
            s = sub_line[sub_line["season"] == ssn]
            s_np = s[~s["push"]]
            s_hits = int(s_np["hit"].sum())
            s_miss = len(s_np) - s_hits
            s_hr = s_hits / len(s_np) if len(s_np) > 0 else 0
            s_roi_u = s_hits * (100 / 110) - s_miss
            s_roi = s_roi_u / len(s_np) * 100 if len(s_np) > 0 else 0
            if direction == "UNDER":
                s_edge = (s["close_total"] - s["actual_total"]).mean()
            else:
                s_edge = (s["actual_total"] - s["close_total"]).mean()
            p23.append("  - %s: %d-%d (%.1f%%), ROI %+.1f%%, edge %+.1fpts" % (
                ssn, s_hits, s_miss, s_hr * 100, s_roi, s_edge))

        p23.append("")
        results_all.append({
            "archetype": arch_name, "direction": direction, "window": window_name,
            "n_games": n, "hits": hits, "misses": misses, "pushes": pushes,
            "hit_rate": round(hit_rate, 4), "roi_pct": round(roi_pct, 1),
            "edge_pts": round(edge_pts, 1),
        })

(OUT / "phase23_historical.md").write_text("\n".join(p23))

# ── PHASE 4: Live shadow evidence ───────────────────────────────────
p4 = ["# Phase 4: Live Shadow Evidence (2026 Season)", ""]
try:
    sl = pd.read_parquet("/root/mlb-model/nba/data/nba_signal_log.parquet")
    p4.append("Signal log: %d entries, %s to %s" % (len(sl), sl["game_date"].min(), sl["game_date"].max()))
    p4.append("")

    p4.append("## Signal type distribution")
    for st, cnt in sl["signal_type"].value_counts().items():
        p4.append("- %s: %d" % (st, cnt))
    p4.append("")

    graded = sl[sl["actual_total"].notna() & sl["result"].notna()]
    p4.append("## Graded results by signal type")
    if len(graded) > 0:
        for st in graded["signal_type"].unique():
            sg = graded[graded["signal_type"] == st]
            w = int((sg["result"] == "W").sum())
            l_cnt = int((sg["result"] == "L").sum())
            u = sg["units_won_lost"].sum() if "units_won_lost" in sg.columns else 0
            p4.append("- %s: %dW-%dL, %+.2fu" % (st, w, l_cnt, u))
    p4.append("")

    p4.append("## Venue signal breakdown")
    venue = sl[sl["venue_signal"].notna()]
    if len(venue) > 0:
        vg = venue[venue["actual_total"].notna() & venue["result"].notna()]
        if len(vg) > 0:
            vw = int((vg["result"] == "W").sum())
            vl = len(vg) - vw
            vu = vg["units_won_lost"].sum() if "units_won_lost" in vg.columns else 0
            p4.append("- Venue-tagged: %dW-%dL, %+.2fu" % (vw, vl, vu))
        else:
            p4.append("- Venue signals exist but none graded yet")
    else:
        p4.append("- No venue signals in log")
    p4.append("")

    p4.append("## OREB confirms breakdown")
    oreb = sl[sl["oreb_confirms"] == True]
    if len(oreb) > 0:
        og = oreb[oreb["actual_total"].notna() & oreb["result"].notna()]
        if len(og) > 0:
            ow = int((og["result"] == "W").sum())
            ol = len(og) - ow
            ou = og["units_won_lost"].sum() if "units_won_lost" in og.columns else 0
            p4.append("- OREB confirms: %dW-%dL, %+.2fu" % (ow, ol, ou))
        else:
            p4.append("- OREB confirms exist but none graded yet")
    else:
        p4.append("- No OREB confirms in log")
    p4.append("")
except Exception as e:
    p4.append("Error: " + str(e))

# Phase 6 RS shadow
try:
    p6 = pd.read_parquet("/root/mlb-model/nba/data/nba_phase6_rs_shadow.parquet")
    p4.append("## Phase 6 RS Shadow")
    p4.append("Entries: %d" % len(p6))
    g6 = p6[p6["result"].notna()]
    if len(g6) > 0:
        w6 = int((g6["result"] == "W").sum())
        l6 = len(g6) - w6
        p4.append("Record: %dW-%dL" % (w6, l6))
        if "roi_outcome" in g6.columns:
            p4.append("ROI units: %+.2f" % g6["roi_outcome"].sum())
    p4.append("")
except Exception as e:
    p4.append("Phase 6 shadow error: " + str(e))

(OUT / "phase4_live_shadow.md").write_text("\n".join(p4))

# ── PHASE 5-6: Verdicts ─────────────────────────────────────────────
verdicts = []
p56 = ["# Phase 5-6: Verdicts & Keep/Kill", ""]

for arch_name, arch in ARCHETYPES.items():
    oos_rows = [r for r in results_all if r["archetype"] == arch_name and "TRUE_OOS" in r["window"]]
    ins_rows = [r for r in results_all if r["archetype"] == arch_name and "IN_SAMPLE" in r["window"]]
    oos = oos_rows[0] if oos_rows else None
    ins = ins_rows[0] if ins_rows else None

    p56.append("## " + arch_name)
    p56.append("Direction: " + arch["direction"])

    if oos and oos["n_games"] >= 20:
        p56.append("TRUE OOS: %d-%d (%.1f%%), ROI %+.1f%%, edge %+.1fpts" % (
            oos["hits"], oos["misses"], oos["hit_rate"] * 100, oos["roi_pct"], oos["edge_pts"]))
    elif oos:
        p56.append("TRUE OOS: %d-%d (%.1f%%), ROI %+.1f%% [SMALL SAMPLE n=%d]" % (
            oos["hits"], oos["misses"], oos["hit_rate"] * 100, oos["roi_pct"], oos["n_games"]))

    if ins:
        p56.append("In-sample: %d-%d (%.1f%%), ROI %+.1f%%, edge %+.1fpts" % (
            ins["hits"], ins["misses"], ins["hit_rate"] * 100, ins["roi_pct"], ins["edge_pts"]))

    verdict = "INCONCLUSIVE"
    reason = ""

    if oos and oos["n_games"] >= 20:
        hr = oos["hit_rate"]
        roi = oos["roi_pct"]
        edge = oos["edge_pts"]
        if hr >= 0.54 and roi > 0:
            verdict = "SURVIVES"
            reason = "OOS hit rate %.1f%% with positive ROI %+.1f%%" % (hr * 100, roi)
        elif hr >= 0.52 and roi > -3:
            verdict = "SURVIVES"
            reason = "OOS hit rate %.1f%% marginal but viable (ROI %+.1f%%)" % (hr * 100, roi)
        elif hr >= 0.50 and edge > 0:
            verdict = "DIMINISHED"
            reason = "OOS hit rate %.1f%% at breakeven, edge %+.1fpts positive but thin" % (hr * 100, edge)
        elif hr < 0.48:
            verdict = "COLLAPSES"
            reason = "OOS hit rate %.1f%% below breakeven, ROI %+.1f%%" % (hr * 100, roi)
        elif roi < -8:
            verdict = "COLLAPSES"
            reason = "OOS ROI %+.1f%% severely negative" % roi
        else:
            verdict = "DIMINISHED"
            reason = "OOS hit rate %.1f%%, ROI %+.1f%% -- not convincing" % (hr * 100, roi)
    elif oos and oos["n_games"] < 20:
        verdict = "INCONCLUSIVE"
        reason = "Only %d OOS games -- insufficient for verdict" % oos["n_games"]

    p56.append("")
    p56.append("**VERDICT: " + verdict + "**")
    p56.append("Reason: " + reason)
    p56.append("")

    verdicts.append({
        "archetype": arch_name, "direction": arch["direction"], "verdict": verdict, "reason": reason,
        "oos_n": oos["n_games"] if oos else 0,
        "oos_hit_rate": oos["hit_rate"] if oos else None,
        "oos_roi": oos["roi_pct"] if oos else None,
        "oos_edge": oos["edge_pts"] if oos else None,
        "ins_n": ins["n_games"] if ins else 0,
        "ins_hit_rate": ins["hit_rate"] if ins else None,
        "ins_roi": ins["roi_pct"] if ins else None,
    })

(OUT / "phase56_verdicts.md").write_text("\n".join(p56))

# CSV
pd.DataFrame(results_all).to_csv(OUT / "archetype_results.csv", index=False)
pd.DataFrame(verdicts).to_csv(OUT / "archetype_verdicts.csv", index=False)

# ── KEEP/KILL MEMO ──────────────────────────────────────────────────
memo = [
    "# NBA Current Archetypes -- Keep/Kill Memo",
    "Generated: 2026-04-10",
    "Data: 3 seasons (2022-23 through 2024-25), %d games" % len(df),
    "TRUE OOS window: 2022-23, 2023-24 (pre-discovery)",
    "In-sample window: 2024-25 (discovery/contaminated)",
    "",
    "## Summary Table",
    "",
    "| Archetype | Dir | OOS N | OOS Hit% | OOS ROI | InS Hit% | InS ROI | Verdict |",
    "|-----------|-----|-------|----------|---------|----------|---------|---------|",
]

for v in verdicts:
    oos_hr = "%.1f%%" % (v["oos_hit_rate"] * 100) if v["oos_hit_rate"] is not None else "N/A"
    oos_roi = "%+.1f%%" % v["oos_roi"] if v["oos_roi"] is not None else "N/A"
    ins_hr = "%.1f%%" % (v["ins_hit_rate"] * 100) if v["ins_hit_rate"] is not None else "N/A"
    ins_roi = "%+.1f%%" % v["ins_roi"] if v["ins_roi"] is not None else "N/A"
    memo.append("| %s | %s | %d | %s | %s | %s | %s | **%s** |" % (
        v["archetype"], v["direction"], v["oos_n"], oos_hr, oos_roi, ins_hr, ins_roi, v["verdict"]))

memo.append("")
memo.append("## Detailed Verdicts")
memo.append("")
for v in verdicts:
    action_map = {"SURVIVES": "KEEP", "DIMINISHED": "MONITOR", "COLLAPSES": "KILL", "INCONCLUSIVE": "PAUSE"}
    action = action_map.get(v["verdict"], "?")
    memo.append("### %s -- %s (%s)" % (v["archetype"], v["verdict"], action))
    memo.append("- " + v["reason"])
    memo.append("")

memo.append("## Methodology")
memo.append("- Frozen team sets from nba/run_nba.py applied to all historical games")
memo.append("- Graded against real DK/FD closing lines from nba/data/nba_historical_closing_lines.parquet")
memo.append("- ROI computed at standard -110 juice")
memo.append("- Hit rate excludes pushes (actual == line)")
memo.append("- TRUE OOS = seasons that predate the archetype discovery work")
memo.append("- 52.4% is breakeven at -110")

(OUT / "NBA_CURRENT_ARCHETYPES_KEEP_KILL.md").write_text("\n".join(memo))

# ── STDOUT SUMMARY ──────────────────────────────────────────────────
print("=" * 70)
print("NBA ARCHETYPE REVALIDATION -- SUMMARY")
print("=" * 70)
print()
for v in verdicts:
    oos_hr = "%.1f%%" % (v["oos_hit_rate"] * 100) if v["oos_hit_rate"] is not None else "N/A"
    oos_roi = "%+.1f%%" % v["oos_roi"] if v["oos_roi"] is not None else "N/A"
    print("%-40s  OOS: %6s / %7s  ->  %s" % (v["archetype"], oos_hr, oos_roi, v["verdict"]))
print()
print("Files written to " + str(OUT) + "/")
for f in sorted(os.listdir(OUT)):
    if not f.endswith(".py"):
        print("  " + f)
