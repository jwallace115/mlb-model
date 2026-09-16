#!/usr/bin/env python3
"""Phase 5A-8: close-game / key-number diagnostic.

Where does the sim lose its close games?  Compare, sim vs actual (2021-2024 REG):
  * the score-state distribution the first time the Q4 clock reads <= 5:00 and <= 2:00
  * the final-margin distribution conditional on that state
  * what happens in the last 5:00 / 2:00 (final minus snapshot margin) by state

Actual side: first play row (any play type, posteam present) in Q4 with
quarter_seconds_remaining <= 300 (<= 120); pre-play score from posteam_score /
defteam_score mapped to home - away.  Sim side: engine outputs m_q4_300 / m_q4_120
(same definition: score at the start of the first play with the Q4 clock <= 300 / 120).

Usage:
  python nfl/sim/close_game_diagnostic.py actual              -> writes actual table
  python nfl/sim/close_game_diagnostic.py compare <k1.parquet> -> prints comparison
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
PBP = ROOT / "nfl" / "data" / "pbp"
SEASONS = [2021, 2022, 2023, 2024]
ACTUAL_OUT = ROOT / "nfl" / "data" / "sim" / "tables" / "actual_close_games_2021_2024.parquet"

COLS = ["game_id", "season", "week", "season_type", "play_id", "qtr", "quarter_seconds_remaining",
        "posteam", "home_team", "away_team", "posteam_score", "defteam_score",
        "home_score", "away_score", "yardline_100"]


def build_actual() -> pd.DataFrame:
    rows = []
    for s in SEASONS:
        df = pd.read_parquet(PBP / f"pbp_{s}.parquet", columns=COLS)
        df = df[(df.season_type == "REG") & (df.week <= 18)]
        df = df.sort_values(["game_id", "play_id"])
        for gid, g in df.groupby("game_id", sort=False):
            home = g.home_team.iloc[0]
            final = int(g.home_score.iloc[0] - g.away_score.iloc[0])
            ot = bool((g.qtr >= 5).any())
            rec = {"game_id": gid, "season": s, "week": int(g.week.iloc[0]),
                   "final_margin": final, "ot": ot}
            q4 = g[(g.qtr == 4) & g.posteam.notna() & g.posteam_score.notna()]
            for sec, tag in ((300, "300"), (120, "120")):
                h = q4[q4.quarter_seconds_remaining <= sec]
                if len(h) == 0:
                    rec[f"m_q4_{tag}"] = np.nan; rec[f"poss_q4_{tag}"] = np.nan
                    if tag == "120": rec["yl_q4_120"] = np.nan
                    continue
                r = h.iloc[0]
                sign = 1 if r.posteam == home else -1
                rec[f"m_q4_{tag}"] = sign * (r.posteam_score - r.defteam_score)
                rec[f"poss_q4_{tag}"] = 0 if r.posteam == home else 1
                if tag == "120":
                    rec["yl_q4_120"] = r.yardline_100
            rows.append(rec)
    out = pd.DataFrame(rows)
    return out


# ── shared binning ──────────────────────────────────────────────────────────

STATE_BINS = [("tied", 0, 0), ("1-3", 1, 3), ("4-7", 4, 7), ("8-14", 8, 14), ("15+", 15, 999)]


def state_bucket(m):
    a = np.abs(np.asarray(m, dtype=float))
    out = np.full(a.shape, "", dtype=object)
    for lab, lo, hi in STATE_BINS:
        out[(a >= lo) & (a <= hi)] = lab
    return out


def summarize(df: pd.DataFrame, label: str, weights=None) -> dict:
    """Per-game (actual) or per-sim (sim) frame with final_margin, m_q4_300, m_q4_120, ot."""
    fm = df.final_margin.to_numpy(); afm = np.abs(fm)
    d = {"label": label, "n": len(df)}
    for k in (0, 1, 3, 6, 7):
        d[f"P(|final|={k})"] = (afm == k).mean()
    d["P(|final|<=3)"] = (afm <= 3).mean()
    d["P(|final|<=7)"] = (afm <= 7).mean()
    d["P(OT)"] = df.ot.mean()
    d["SD final"] = fm.std()
    for tag in ("300", "120"):
        m = df[f"m_q4_{tag}"].to_numpy(dtype=float)
        sb = state_bucket(m)
        for lab, _, _ in STATE_BINS:
            d[f"P(state@{tag}={lab})"] = (sb == lab).mean()
        d[f"SD m@{tag}"] = np.nanstd(m)
    return d


def conditional_table(df: pd.DataFrame, tag: str) -> pd.DataFrame:
    """Rows: state bucket at the snapshot; cols: P(final key numbers | state), mean |Δ|."""
    m = df[f"m_q4_{tag}"].to_numpy(dtype=float)
    sb = state_bucket(m)
    fm = df.final_margin.to_numpy(dtype=float); afm = np.abs(fm)
    delta = np.abs(fm - m)  # points scored by either side after the snapshot (net)
    rows = []
    for lab, _, _ in STATE_BINS:
        k = sb == lab
        if k.sum() == 0:
            continue
        rows.append({"state": lab, "n": int(k.sum()), "share": k.mean(),
                     "P(final tie)": (afm[k] == 0).mean(),
                     "P(|final|=3)": (afm[k] == 3).mean(),
                     "P(|final|<=3)": (afm[k] <= 3).mean(),
                     "P(|final|<=7)": (afm[k] <= 7).mean(),
                     "P(|final|>=15)": (afm[k] >= 15).mean(),
                     "P(no change)": (delta[k] == 0).mean(),
                     "mean |Δ|": delta[k].mean(),
                     "P(OT)": df.ot.to_numpy()[k].mean(),
                     "P(lead flips)": ((np.sign(fm[k]) != np.sign(m[k])) & (m[k] != 0) & (fm[k] != 0)).mean()})
    return pd.DataFrame(rows).set_index("state")


def delta_hist(df: pd.DataFrame, tag: str, state_labels=("tied", "1-3", "4-7")) -> pd.Series:
    """Distribution of the net change (final - snapshot), signed toward the leader at the snapshot,
    for one-score states.  +x = leader extends by x, -x = trailer closes by x."""
    m = df[f"m_q4_{tag}"].to_numpy(dtype=float)
    fm = df.final_margin.to_numpy(dtype=float)
    sb = state_bucket(m)
    k = np.isin(sb, state_labels)
    sgn = np.where(m[k] >= 0, 1.0, -1.0)
    d = sgn * (fm[k] - m[k])
    d = np.clip(d, -21, 21)
    return pd.Series(d).value_counts(normalize=True).sort_index()


def _pct(x):
    return f"{100*x:5.1f}%"


def compare(k1_path: Path):
    act = pd.read_parquet(ACTUAL_OUT)
    sim = pd.read_parquet(k1_path)
    sim = sim.rename(columns={})
    sim["final_margin"] = sim.home_score - sim.away_score
    sim["ot"] = sim["ot_flag"].astype(bool) if "ot_flag" in sim else (sim.get("ot", 0) > 0)
    n0 = len(sim)
    miss = {c: int((sim[c] == -999).sum()) for c in ("m_q4_300", "m_q4_120")}
    sim = sim[(sim.m_q4_300 != -999) & (sim.m_q4_120 != -999)].copy()
    print(f"actual games: {len(act)}   sim games: {sim.game_id.nunique()}  sims: {n0}  "
          f"(dropped: snapshot never reached {miss} — a single play's runoff carried the clock "
          f"from >120 s to <=0; clock-table q100 is 118 s before pace)\n")

    # 1. unconditional
    rows = [summarize(act, "actual"), summarize(sim, "sim")]
    t = pd.DataFrame(rows).set_index("label").T
    t["diff (sim-act)"] = t["sim"] - t["actual"]
    print("== 1. Unconditional: final margin and snapshot-state distributions ==")
    with pd.option_context("display.float_format", "{:.4f}".format, "display.width", 200):
        print(t.to_string()); print()

    # 2. conditional on state at 5:00 and 2:00
    for tag in ("300", "120"):
        ca = conditional_table(act, tag); cs = conditional_table(sim, tag)
        print(f"== 2. Conditional on |margin| when the Q4 clock first reads <= {int(tag)//60}:{int(tag)%60:02d} ==")
        for col in ["share", "P(final tie)", "P(|final|=3)", "P(|final|<=3)", "P(|final|<=7)",
                    "P(|final|>=15)", "P(no change)", "mean |Δ|", "P(OT)", "P(lead flips)"]:
            print(f"  {col:16s} " + "  ".join(
                f"{lab}: act {ca.loc[lab, col]:.3f} sim {cs.loc[lab, col]:.3f}" for lab in ca.index))
        print("  n (actual games): " + ", ".join(f"{lab} {int(ca.loc[lab,'n'])}" for lab in ca.index))
        print()

    # 3. net-change histogram in one-score states
    for tag in ("300", "120"):
        ha = delta_hist(act, tag); hs = delta_hist(sim, tag)
        idx = sorted(set(ha.index) | set(hs.index))
        print(f"== 3. Net change after the {int(tag)//60}:{int(tag)%60:02d} snapshot, one-score states (|m|<=7); "
              f"+ = leader extends, - = trailer closes ==")
        print("  Δ      actual    sim")
        for i in idx:
            print(f"  {int(i):+3d}   {_pct(ha.get(i, 0.0))}  {_pct(hs.get(i, 0.0))}")
        print()

    # 4. by-season (aggregate hiding)
    print("== 4. By season: P(|final|<=7), P(|final|=3), P(state@5:00 one-score) ==")
    for s in SEASONS:
        a = act[act.season == s]; b = sim[sim.season == s]
        sa = state_bucket(a.m_q4_300); sbb = state_bucket(b.m_q4_300)
        print(f"  {s}: |final|<=7 act {(a.final_margin.abs()<=7).mean():.3f} sim {(b.final_margin.abs()<=7).mean():.3f} | "
              f"|final|=3 act {(a.final_margin.abs()==3).mean():.3f} sim {(b.final_margin.abs()==3).mean():.3f} | "
              f"one-score@5:00 act {np.isin(sa, ['tied','1-3','4-7']).mean():.3f} sim {np.isin(sbb, ['tied','1-3','4-7']).mean():.3f}")
    print()

    # 5. who has the ball at 2:00 in one-score games, and where
    print("== 5. One-score games (|m|<=7) at 2:00: trailer has the ball; trailer field position ==")
    for lab, d in (("actual", act), ("sim", sim)):
        m = d.m_q4_120.to_numpy(dtype=float); one = np.abs(m) <= 7
        poss = d.poss_q4_120.to_numpy(dtype=float)
        # trailer has ball: home trailing (m<0) and poss==0, or away trailing (m>0) and poss==1
        trail_ball = ((m < 0) & (poss == 0)) | ((m > 0) & (poss == 1))
        tied = m == 0
        yl = d.yl_q4_120.to_numpy(dtype=float)
        k = one & ~tied
        print(f"  {lab}: P(trailer has ball | one-score, not tied) {trail_ball[k].mean():.3f}  "
              f"median yardline_100 of possessor {np.nanmedian(yl[one]):.0f}  "
              f"P(possessor inside 40) {(yl[one] <= 40).mean():.3f}")
    print()

    # 6. lead-holder behaviour: P(final == snapshot) i.e. no more points in last 5:00 / 2:00
    print("== 6. P(no points by either team after the snapshot), by state ==")
    for tag in ("300", "120"):
        for lab, d in (("actual", act), ("sim", sim)):
            m = d[f"m_q4_{tag}"].to_numpy(dtype=float); fm = d.final_margin.to_numpy(dtype=float)
            sb = state_bucket(m)
            print(f"  @{tag}s {lab}: " + "  ".join(f"{s}: {(fm[sb==s]==m[sb==s]).mean():.3f}" for s, _, _ in STATE_BINS))
    print()


# ── Late-drive decomposition: what does each drive that starts in the last 5:00 (or OT) do? ──

LATE_DRIVES_ACTUAL = ROOT / "nfl" / "data" / "sim" / "tables" / "actual_late_drives_2021_2024.parquet"
RESULT_MAP_ACTUAL = {"Touchdown": "TD", "Field goal": "FG_made", "Punt": "punt",
                     "Turnover": "turnover", "Opp touchdown": "turnover", "Turnover on downs": "downs",
                     "End of half": "end_game", "Missed field goal": "FG_missed", "Safety": "safety"}
RESULT_MAP_SIM = {"TD": "TD", "FG_made": "FG_made", "punt": "punt", "turnover_int": "turnover",
                  "turnover_fumble": "turnover", "downs": "downs", "end_game": "end_game",
                  "end_half": "end_game", "FG_missed": "FG_missed", "safety": "safety"}
RESULTS = ["TD", "FG_made", "FG_missed", "punt", "turnover", "downs", "end_game", "safety"]
SD_BINS = [("trail9+", -99, -9), ("trail4-8", -8, -4), ("trail1-3", -3, -1), ("tied", 0, 0),
           ("lead1-3", 1, 3), ("lead4-8", 4, 8), ("lead9+", 9, 99)]


def sd_bucket(sd):
    sd = np.asarray(sd, dtype=float)
    out = np.full(sd.shape, "", dtype=object)
    for lab, lo, hi in SD_BINS:
        out[(sd >= lo) & (sd <= hi)] = lab
    return out


def build_actual_late_drives() -> pd.DataFrame:
    cols = ["game_id", "season", "week", "season_type", "play_id", "qtr", "quarter_seconds_remaining",
            "posteam", "posteam_score", "defteam_score", "fixed_drive", "fixed_drive_result",
            "drive_end_transition", "yardline_100"]
    rows = []
    for s in SEASONS:
        df = pd.read_parquet(PBP / f"pbp_{s}.parquet", columns=cols)
        df = df[(df.season_type == "REG") & (df.week <= 18) & df.posteam.notna() & df.posteam_score.notna()]
        df = df.sort_values(["game_id", "play_id"])
        first = df.groupby(["game_id", "fixed_drive"], sort=False).head(1)
        late = first[((first.qtr == 4) & (first.quarter_seconds_remaining <= 300)) | (first.qtr >= 5)]
        for _, r in late.iterrows():
            res = RESULT_MAP_ACTUAL.get(r.fixed_drive_result)
            if res is None:
                continue
            opp_td = r.fixed_drive_result == "Opp touchdown"
            rows.append({"game_id": r.game_id, "season": s, "start_quarter": int(r.qtr),
                         "start_clock": float(r.quarter_seconds_remaining),
                         "start_yardline": float(r.yardline_100),
                         "sd_start": int(r.posteam_score - r.defteam_score),
                         "result": res, "opp_td": bool(opp_td)})
    return pd.DataFrame(rows)


def run_sim_late_drives(out_path: Path, n_sims: int = 500):
    """Full K1 protocol (1,087 games x N) with the drive log on; keep only drives that start
    in the last 5:00 of Q4 or in OT, so memory stays small."""
    import time
    from nfl.sim.engine import simulate_game, _load_tables, _load_ratings
    from nfl.sim.seed_util import stable_seed
    _load_tables(); team_r, tend, sit, kicker, league = _load_ratings()
    kw = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league)
    keep = []
    for s in SEASONS:
        gdf = pd.read_parquet(PBP / f"pbp_{s}.parquet", columns=["game_id", "week", "home_team", "away_team"])
        games = gdf.drop_duplicates("game_id").query("week <= 18"); t0 = time.time()
        for _, g in games.iterrows():
            r = simulate_game(g.home_team, g.away_team, s, int(g.week), n_sims=n_sims,
                              seed=stable_seed((g.game_id, 42)), drive_log=True, **kw)
            r = r[0] if isinstance(r, tuple) else r
            dl = r.attrs["drive_log"]
            late = dl[((dl.start_quarter == 4) & (dl.start_clock <= 300)) | (dl.start_quarter >= 5)].copy()
            late["game_id"] = g.game_id; late["season"] = s
            keep.append(late)
        pd.concat(keep, ignore_index=True).to_parquet(out_path, index=False)
        print(f"season {s} done {time.time()-t0:.0f}s, rows so far {sum(len(k) for k in keep)}", flush=True)
    print("DONE", flush=True)


def compare_drives(sim_path: Path):
    act = pd.read_parquet(LATE_DRIVES_ACTUAL)
    sim = pd.read_parquet(sim_path)
    sim["result"] = sim["result"].map(RESULT_MAP_SIM)
    sim["opp_td"] = sim["opp_points"] >= 6
    n_games_act = act.game_id.nunique(); n_sim_games = 543500 - 0  # 1,087 x 500
    print(f"actual late drives: {len(act)} in {n_games_act} games ({len(act)/1087:.2f}/game); "
          f"sim: {len(sim)} in 1,087 x 500 sims ({len(sim)/543500:.2f}/game)\n")

    for window, name in (("q4_300", "Q4 <= 5:00"), ("q4_120", "Q4 <= 2:00"), ("ot", "OT")):
        if window == "q4_300":
            ka = (act.start_quarter == 4) & (act.start_clock <= 300); ks = (sim.start_quarter == 4) & (sim.start_clock <= 300)
        elif window == "q4_120":
            ka = (act.start_quarter == 4) & (act.start_clock <= 120); ks = (sim.start_quarter == 4) & (sim.start_clock <= 120)
        else:
            ka = act.start_quarter >= 5; ks = sim.start_quarter >= 5
        a = act[ka]; b = sim[ks]
        print(f"== Drives starting in {name}: {len(a)/1087:.2f}/game actual vs {len(b)/543500:.2f}/game sim ==")
        print("  result mix by offence score state at drive start (act | sim), share of drives in that state")
        for lab, _, _ in SD_BINS:
            aa = a[sd_bucket(a.sd_start) == lab]; bb = b[sd_bucket(b.sd_start) == lab]
            if len(aa) == 0 and len(bb) == 0:
                continue
            ra = aa.result.value_counts(normalize=True); rb = bb.result.value_counts(normalize=True)
            print(f"  {lab:9s} n_act {len(aa):4d} ({len(aa)/max(len(a),1):.3f})  n_sim/game {len(bb)/543500:.3f} ({len(bb)/max(len(b),1):.3f})")
            print("           " + "  ".join(f"{res}: {ra.get(res,0):.3f}|{rb.get(res,0):.3f}" for res in RESULTS)
                  + f"  oppTD: {aa.opp_td.mean():.3f}|{bb.opp_td.mean():.3f}")
        print()

    # FG range reached but no kick: in tied / trail1-3 states in the last 2:00, how often does the drive end
    # with the offence inside the 35 (end_yardline <= 35) without a FG attempt?  (sim only: end_yardline exists)
    if "end_yardline" in sim:
        b = sim[(sim.start_quarter == 4) & (sim.start_clock <= 120)]
        for lab in ("tied", "trail1-3", "lead1-3"):
            bb = b[sd_bucket(b.sd_start) == lab]
            inrange_nokick = bb[(bb.end_yardline <= 35) & ~bb.result.isin(["FG_made", "FG_missed", "TD"])]
            print(f"  sim {lab} drives starting <= 2:00: ended inside the 35 without a kick or TD: "
                  f"{len(inrange_nokick)/max(len(bb),1):.3f} (results: {inrange_nokick.result.value_counts().to_dict()})")
    print()


if __name__ == "__main__":
    if sys.argv[1] == "drives_actual":
        out = build_actual_late_drives()
        out.to_parquet(LATE_DRIVES_ACTUAL, index=False)
        print(f"wrote {LATE_DRIVES_ACTUAL} ({len(out)} drives)")
    elif sys.argv[1] == "drives_sim":
        run_sim_late_drives(Path(sys.argv[2]))
    elif sys.argv[1] == "drives_compare":
        compare_drives(Path(sys.argv[2]))
    elif sys.argv[1] == "actual":
        out = build_actual()
        out.to_parquet(ACTUAL_OUT, index=False)
        print(f"wrote {ACTUAL_OUT} ({len(out)} games); missing m_q4_300: {out.m_q4_300.isna().sum()}, "
              f"m_q4_120: {out.m_q4_120.isna().sum()}")
    elif sys.argv[1] == "compare":
        compare(Path(sys.argv[2]))
