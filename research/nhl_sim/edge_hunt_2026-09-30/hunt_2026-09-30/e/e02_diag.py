#!/usr/bin/env python3
"""E-02 diagnostic D1/D2: fresh quotes only, no events in the prior 120 s, power de-vig."""
import gzip, json, glob, numpy as np, pandas as pd, sys
sys.path.insert(0, "/home/claude/hunt/e")
from e02_report import cluster_boot_a1, cluster_se
H = "/home/claude/hunt"; E = f"{H}/e"
from scipy.optimize import brentq
def ll(y, p): p = np.clip(p, 1e-3, 1 - 1e-3); return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))
def power_fair(ih, ia):
    f = lambda k: ih ** k + ia ** k - 1
    try:
        k = brentq(f, 0.5, 50.0)
    except ValueError:
        return ih / (ih + ia)
    return ih ** k
D = pd.read_parquet(f"{E}/e02_rows.parquet")
U = pd.read_parquet(f"{E}/inplay_last_update.parquet")
U["ts"] = pd.to_datetime(U.ts)
ages = U[U.market == "h2h"].pivot_table(index=["ts", "event_id"], columns="bookmaker", values="age_s")
books = [c[:-6] for c in D.columns if c.endswith("_dec_h")]
# recent events: ESPN goals/penalties within 120 s before ts
T = pd.read_parquet(f"{E}/state_at_snapshot_2023.parquet")
ev = {}
ALIAS = {"NJ": "NJD", "TB": "TBL", "LA": "LAK", "SJ": "SJS"}
G = pd.read_parquet(f"{H}/research/nhl_sim/edge_hunt_2026-09-30/games_lines.parquet"); G = G[G.season == 2023]
for f in sorted(glob.glob(f"{E}/nhl/cache/espn_pbp/*.json.gz")):
    j = json.load(gzip.open(f)); comp = j["header"]["competitions"][0]
    teams = {c["homeAway"]: ALIAS.get(c["team"]["abbreviation"], c["team"]["abbreviation"]) for c in comp["competitors"]}
    d = pd.Timestamp(comp["date"]); cand = G[(G.home == teams["home"]) & (G.away == teams["away"]) & ((G.ct - d).abs() < pd.Timedelta("12h"))]
    if len(cand) != 1: continue
    ev[int(cand.game_id.iloc[0])] = [pd.Timestamp(p["wallclock"]) for p in j.get("plays", []) if p["type"]["text"] in ("Goal", "Penalty")]
def recent_event(r, w=120):
    return any(0 <= (r.ts - t).total_seconds() <= w for t in ev.get(int(r.game_id), []))
D["recent_ev"] = [recent_event(r) for r in D.itertuples()]
# fresh quotes
fair_m, fair_p, bh, ba = [], [], [], []
for b in books:
    age = ages[b].reindex(pd.MultiIndex.from_arrays([D.ts, D.event_id])).to_numpy() if b in ages else np.full(len(D), np.nan)
    fresh = age <= 30
    ih, ia = 1 / D[f"{b}_dec_h"].to_numpy(), 1 / D[f"{b}_dec_a"].to_numpy()
    fm = np.where(fresh, ih / (ih + ia), np.nan)
    fp = np.array([power_fair(x, y) if (fr and np.isfinite(x) and np.isfinite(y)) else np.nan for x, y, fr in zip(ih, ia, fresh)])
    fair_m.append(fm); fair_p.append(fp); bh.append(np.where(fresh, D[f"{b}_dec_h"], np.nan)); ba.append(np.where(fresh, D[f"{b}_dec_a"], np.nan))
FM, FP, BH, BA = [np.column_stack(x) for x in (fair_m, fair_p, bh, ba)]
D["med_m_fresh"] = np.nanmedian(FM, axis=1); D["med_p_fresh"] = np.nanmedian(FP, axis=1)
D["n_fresh"] = np.isfinite(FM).sum(axis=1); D["best_h_fresh"] = np.nanmax(BH, axis=1); D["best_a_fresh"] = np.nanmax(BA, axis=1)
print(f"rows {len(D)}; rows with >=3 fresh (<=30 s) h2h quotes: {int((D.n_fresh>=3).sum())}; with a goal/penalty in prior 120 s: {int(D.recent_ev.sum())}")
def block(x, label):
    y = x.y_home.to_numpy(); pe = x.e_p_home.to_numpy()
    for nm, pp in [("mult", x.med_m_fresh.to_numpy()), ("power", x.med_p_fresh.to_numpy())]:
        b, lo, hi, p = cluster_boot_a1(y, pe, pp, x.game_id.to_numpy(), B=500)
        print(f"{label} [{nm}] n={len(x)} games={x.game_id.nunique()} LL engine {ll(y, pe):.4f} median {ll(y, pp):.4f} | A1 {b:+.3f} [{lo:+.3f}, {hi:+.3f}] p={p:.4f}")
    ea = pe - 1 / x.best_h_fresh.to_numpy(); eb = (1 - pe) - 1 / x.best_a_fresh.to_numpy(); pa, pb = ea >= 0.05, eb >= 0.05
    ret = np.concatenate([np.where(y == 1, x.best_h_fresh.to_numpy() - 1, -1.0)[pa], np.where(y == 0, x.best_a_fresh.to_numpy() - 1, -1.0)[pb]])
    grp = np.concatenate([x.game_id.to_numpy()[pa], x.game_id.to_numpy()[pb]])
    if len(ret) > 1:
        se = cluster_se(ret, grp); print(f"   A2 picks {len(ret)} games {len(np.unique(grp))} ROI {ret.mean():+.4f} (clustered SE {se:.4f}, 90% lo {ret.mean()-1.6449*se:+.4f})")
    bk = pd.DataFrame({"ret": ret, "bucket": np.concatenate([x.bucket.astype(str).to_numpy()[pa], x.bucket.astype(str).to_numpy()[pb]])})
    if len(bk): print(bk.groupby("bucket").ret.agg(["size", "mean"]).round(3).to_string())
base = D[(D.n_fresh >= 3)]
block(base, "FRESH<=30s, any events")
block(base[~base.recent_ev], "FRESH<=30s + NO goal/penalty in prior 120 s")
block(base[base.recent_ev], "FRESH<=30s + event in prior 120 s (should hold the artefact)")
pp_ = base[~base.recent_ev & (base.phase == "live") & (base.home_skaters != base.away_skaters) & (base.home_goalie == 1) & (base.away_goalie == 1)]
block(pp_, "S2 power play, fresh, no recent event")
