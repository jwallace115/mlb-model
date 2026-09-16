#!/usr/bin/env python3
"""Phase 5A-10: scoring-event composition diagnostic.

5A-9 showed the sim's margin histogram is a smoothed version of reality already at 5:00
(mass at 3/6/10 too low, 1/2/4/9/11/13 too high) although the per-team means of TDs and
FGs are right. This compares the COMPOSITION: per team, how many TDs (by PAT outcome:
7 / 6 / 8), FGs made and missed, defensive/special-teams TDs and safeties, and how the two
teams' counts combine into the margin.

Actual side (2021-2024 REG, per game per team, from pbp play rows):
  td7 / td6 / td8  = offensive TD drives by points credited (XP made / no XP or missed /
                     two-point made), counted from the scoring play + the try that follows
  fg / fgmiss      = field goals made / missed by the offence
  opp_td           = TDs scored by the opponent while THIS team had the ball (pick-six,
                     fumble return, punt return) -> credited to the opponent's score
  opp_saf          = safeties conceded by this team
  q4_td / q4_fg    = TDs / FGs on drives that STARTED in Q4 or OT (the engine's definition)
Sim side: the same counts from the engine drive log (points / opp_points per drive).
Both sides are checked against the final score before anything is compared.

Usage:
  python nfl/sim/scoring_composition.py actual                 -> writes actual table
  python nfl/sim/scoring_composition.py compare <comp.parquet>  -> prints the comparison
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PBP = ROOT / "nfl" / "data" / "pbp"
SEASONS = [2021, 2022, 2023, 2024]
ACTUAL_OUT = ROOT / "nfl" / "data" / "sim" / "tables" / "actual_scoring_composition_2021_2024.parquet"

COLS = ["game_id", "season", "week", "season_type", "play_id", "qtr", "posteam", "defteam", "home_team",
        "away_team", "home_score", "away_score", "touchdown", "td_team", "extra_point_result",
        "two_point_conv_result", "field_goal_result", "safety", "play_type", "sp", "fixed_drive_result", "fixed_drive"]


def build_actual() -> pd.DataFrame:
    rows = []
    for s in SEASONS:
        df = pd.read_parquet(PBP / f"pbp_{s}.parquet", columns=COLS)
        df = df[(df.season_type == "REG") & (df.week <= 18)].sort_values(["game_id", "play_id"])
        for gid, g in df.groupby("game_id", sort=False):
            home, away = g.home_team.iloc[0], g.away_team.iloc[0]
            fin = {home: int(g.home_score.iloc[0]), away: int(g.away_score.iloc[0])}
            rec = {t: dict(td7=0, td6=0, td8=0, fg=0, fgmiss=0, opp_td=0, opp_saf=0, q4_fg=0, q4_td=0) for t in (home, away)}
            g = g.reset_index(drop=True)
            # q4_* are counted by the quarter the DRIVE STARTED in, which is what the engine's
            # drive log records (a play-quarter definition under-counts the sim by ~25%)
            drive_q = g[g.play_type.isin(["pass", "run", "punt", "field_goal", "qb_kneel", "qb_spike"])] \
                .groupby("fixed_drive").qtr.first().to_dict()
            for i, r in g.iterrows():
                if r.touchdown == 1 and pd.notna(r.td_team):
                    # the try is on one of the next rows (extra_point_result / two_point_conv_result)
                    pts = 6
                    for j in range(i + 1, min(i + 4, len(g))):
                        nr = g.iloc[j]
                        if pd.notna(nr.extra_point_result):
                            pts = 7 if nr.extra_point_result == "good" else 6
                            break
                        if pd.notna(nr.two_point_conv_result):
                            pts = 8 if nr.two_point_conv_result == "success" else 6
                            break
                    scorer = r.td_team
                    if scorer == r.posteam:
                        rec[scorer][f"td{pts}"] += 1
                        if drive_q.get(r.fixed_drive, r.qtr) >= 4: rec[scorer]["q4_td"] += 1
                    else:
                        # defensive / return TD: the possessing team conceded it
                        other = r.posteam if pd.notna(r.posteam) else (home if scorer == away else away)
                        rec[other]["opp_td"] += 1
                        rec[scorer][f"td{pts}"] += 0  # counted as non-offensive below
                        rec[scorer].setdefault("nonoff_pts", 0)
                        rec[scorer]["nonoff_pts"] = rec[scorer].get("nonoff_pts", 0) + pts
                elif r.play_type == "field_goal" and pd.notna(r.posteam):
                    if r.field_goal_result == "made":
                        rec[r.posteam]["fg"] += 1
                        if drive_q.get(r.fixed_drive, r.qtr) >= 4: rec[r.posteam]["q4_fg"] += 1
                    else:
                        rec[r.posteam]["fgmiss"] += 1
                if r.safety == 1 and pd.notna(r.posteam):
                    rec[r.posteam]["opp_saf"] += 1
            for t in (home, away):
                o = away if t == home else home
                d = rec[t]
                recon = 7 * d["td7"] + 6 * d["td6"] + 8 * d["td8"] + 3 * d["fg"] + d.get("nonoff_pts", 0) + 2 * rec[o]["opp_saf"]
                rows.append({"game_id": gid, "season": s, "team": t, "is_home": int(t == home), "score": fin[t],
                             "recon": recon, **{k: d[k] for k in ("td7", "td6", "td8", "fg", "fgmiss", "opp_td", "opp_saf", "q4_fg", "q4_td")},
                             "nonoff_pts": d.get("nonoff_pts", 0)})
    out = pd.DataFrame(rows)
    return out


def _hist(x, kmax):
    x = np.asarray(x); return np.array([(x == k).mean() for k in range(kmax + 1)])


def compare(path: Path):
    act = pd.read_parquet(ACTUAL_OUT)
    bad = (act.score != act.recon).mean()
    print(f"actual: {act.game_id.nunique()} games; score reconstruction mismatch share {bad:.4f}")
    sim = pd.read_parquet(path)
    sim["td"] = sim.td7 + sim.td6 + sim.td8; act["td"] = act.td7 + act.td6 + act.td8
    # sim reconstruction: offence points + opponent's conceded (def TDs are the OTHER team's opp_td at 6/7/8 -> use score)
    print(f"sim: {sim.game_id.nunique()} games, {len(sim)//2} sims\n")

    print("== 1. Per-team scoring events (mean per team-game) ==")
    for c in ("td", "td7", "td6", "td8", "fg", "fgmiss", "opp_td", "opp_saf", "q4_td", "q4_fg"):
        print(f"  {c:8s} actual {act[c].mean():.3f}   sim {sim[c].mean():.3f}")
    print(f"  {'XP miss|TD':8s} actual {act.td6.sum()/act.td.sum():.3f}   sim {sim.td6.sum()/sim.td.sum():.3f}")
    print(f"  {'2pt|TD':8s} actual {act.td8.sum()/act.td.sum():.3f}   sim {sim.td8.sum()/sim.td.sum():.3f}")
    print(f"  {'FG make':8s} actual {act.fg.sum()/(act.fg.sum()+act.fgmiss.sum()):.3f}   sim {sim.fg.sum()/(sim.fg.sum()+sim.fgmiss.sum()):.3f}\n")

    print("== 2. Distribution of TDs and FGs per team (share of team-games) ==")
    for c, kmax in (("td", 7), ("fg", 6)):
        ha, hs = _hist(act[c], kmax), _hist(sim[c], kmax)
        print(f"  {c}:  k      " + "  ".join(f"{k:5d}" for k in range(kmax + 1)))
        print(f"      actual " + "  ".join(f"{100*v:5.1f}" for v in ha) + f"   var {act[c].var():.3f}")
        print(f"      sim    " + "  ".join(f"{100*v:5.1f}" for v in hs) + f"   var {sim[c].var():.3f}")
    print(f"  corr(td, fg) within team: actual {act[['td','fg']].corr().iloc[0,1]:.3f}  sim {sim[['td','fg']].corr().iloc[0,1]:.3f}\n")

    print("== 3. Joint (TDs, FGs) per team — share of team-games, actual | sim (rows TDs 0-5, cols FGs 0-4) ==")
    for k in range(6):
        ra = [((act.td == k) & (act.fg == j)).mean() for j in range(5)]
        rs = [((sim.td == k) & (sim.fg == j)).mean() for j in range(5)]
        print(f"  TD={k}: " + "  ".join(f"{100*a:4.1f}|{100*b:4.1f}" for a, b in zip(ra, rs)))
    print()

    # 4. game-level: the two teams' compositions and the margin
    def _game(df):
        h = df[df.is_home == 1].set_index("game_id") if "is_home" in df else df[df.team == 0].set_index(["game_id", "sim_id"])
        a = df[df.is_home == 0].set_index("game_id") if "is_home" in df else df[df.team == 1].set_index(["game_id", "sim_id"])
        j = h.join(a, lsuffix="_h", rsuffix="_a")
        j["margin"] = j.score_h - j.score_a
        j["dtd"] = j.td_h - j.td_a; j["dfg"] = j.fg_h - j.fg_a
        j["tot_td"] = j.td_h + j.td_a; j["tot_fg"] = j.fg_h + j.fg_a
        return j
    ga, gs = _game(act), _game(sim)
    print("== 4. Game level ==")
    print(f"  corr(td_h, td_a) actual {ga[['td_h','td_a']].corr().iloc[0,1]:.3f} sim {gs[['td_h','td_a']].corr().iloc[0,1]:.3f}; "
          f"corr(fg_h, fg_a) actual {ga[['fg_h','fg_a']].corr().iloc[0,1]:.3f} sim {gs[['fg_h','fg_a']].corr().iloc[0,1]:.3f}")
    print(f"  SD(td_h - td_a) actual {ga.dtd.std():.3f} sim {gs.dtd.std():.3f};  SD(fg_h - fg_a) actual {ga.dfg.std():.3f} sim {gs.dfg.std():.3f}; "
          f"corr(dtd, dfg) actual {ga[['dtd','dfg']].corr().iloc[0,1]:.3f} sim {gs[['dtd','dfg']].corr().iloc[0,1]:.3f}")
    print(f"  total TDs/game var actual {ga.tot_td.var():.2f} sim {gs.tot_td.var():.2f}; total FGs/game var actual {ga.tot_fg.var():.2f} sim {gs.tot_fg.var():.2f}")
    print("  P(|margin|=3) by |dtd| (TD-count difference), actual | sim, with share of games:")
    for k in range(4):
        ma, ms = ga[ga.dtd.abs() == k], gs[gs.dtd.abs() == k]
        print(f"    |dtd|={k}: share {ma.shape[0]/len(ga):.3f}|{ms.shape[0]/len(gs):.3f}   P(|m|=3) {(ma.margin.abs()==3).mean():.3f}|{(ms.margin.abs()==3).mean():.3f}   "
              f"P(|m|<=3) {(ma.margin.abs()<=3).mean():.3f}|{(ms.margin.abs()<=3).mean():.3f}   P(|dfg|=1 | |dtd|=k) {(ma.dfg.abs()==1).mean():.3f}|{(ms.dfg.abs()==1).mean():.3f}")
    print("  margin decomposition — games with equal TD counts (dtd=0): FG difference histogram, actual | sim")
    ma, ms = ga[ga.dtd == 0], gs[gs.dtd == 0]
    for k in range(-3, 4):
        print(f"    dfg={k:+d}: {100*(ma.dfg==k).mean():5.1f} | {100*(ms.dfg==k).mean():5.1f}")
    print("  games with dtd=0 and dfg=0 (composition tie): P(margin=0) actual {:.3f} sim {:.3f}; share of such games {:.3f}|{:.3f}".format(
        (ma[ma.dfg==0].margin==0).mean(), (ms[ms.dfg==0].margin==0).mean(), (ma.dfg==0).mean()*len(ma)/len(ga), (ms.dfg==0).mean()*len(ms)/len(gs)))
    print()

    print("== 5. Q4 scoring: TDs and FGs in Q4/OT per team, actual | sim, by final |margin| bucket ==")
    for lab, lo, hi in (("<=3", 0, 3), ("4-7", 4, 7), ("8-14", 8, 14), ("15+", 15, 99)):
        ka = ga[(ga.margin.abs() >= lo) & (ga.margin.abs() <= hi)]; ks = gs[(gs.margin.abs() >= lo) & (gs.margin.abs() <= hi)]
        print(f"  |m| {lab:4s}: share {len(ka)/len(ga):.3f}|{len(ks)/len(gs):.3f}  Q4 FG/game {ka.q4_fg_h.mean()+ka.q4_fg_a.mean():.2f}|{ks.q4_fg_h.mean()+ks.q4_fg_a.mean():.2f}  "
              f"Q4 TD/game {ka.q4_td_h.mean()+ka.q4_td_a.mean():.2f}|{ks.q4_td_h.mean()+ks.q4_td_a.mean():.2f}")
    print()

    print("== 6. By season: TDs and FGs per team, XP-miss rate ==")
    for s in SEASONS:
        a, b = act[act.season == s], sim[sim.season == s]
        print(f"  {s}: TD {a.td.mean():.2f}|{b.td.mean():.2f}  FG {a.fg.mean():.2f}|{b.fg.mean():.2f}  XPmiss {a.td6.sum()/a.td.sum():.3f}|{b.td6.sum()/b.td.sum():.3f}  2pt {a.td8.sum()/a.td.sum():.3f}|{b.td8.sum()/b.td.sum():.3f}")


if __name__ == "__main__":
    if sys.argv[1] == "actual":
        out = build_actual(); out.to_parquet(ACTUAL_OUT, index=False)
        print(f"wrote {ACTUAL_OUT} ({len(out)} team-games); score mismatch {(out.score != out.recon).mean():.4f}")
    elif sys.argv[1] == "compare":
        compare(Path(sys.argv[2]))
