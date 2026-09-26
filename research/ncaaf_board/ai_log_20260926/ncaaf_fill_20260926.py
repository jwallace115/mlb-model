"""Fill the NCAAF blind-log sheet from ncaaf_views_20260926.VIEWS. Usage:
   python3 ncaaf_fill_20260926.py <repo_root> <lines_file> <out_csv>"""
import sys, importlib.util
from datetime import datetime, timezone
from math import erf, sqrt
import pandas as pd
root, lines_file, out_csv = sys.argv[1], sys.argv[2], sys.argv[3]
sys.path.insert(0, root)
spec = importlib.util.spec_from_file_location("v", "/home/claude/docs/ncaaf_views_20260926.py"); v = importlib.util.module_from_spec(spec); spec.loader.exec_module(v)
import nfl.pipeline.log_ai_opinions as L
L.set_sport("ncaaf")
now = datetime.now(timezone.utc)
props, lines = L.newest_inputs(2026, now, lines_file=lines_file)
sh = L.build_sheet(props, lines, now)
sh = sh[pd.to_datetime(sh.commence_time) < pd.Timestamp("2026-09-27T08:00:00Z")].copy()   # today's slate only
Phi = lambda x: 0.5 * (1 + erf(x / sqrt(2)))
games = sh.drop_duplicates("event_id")[["event_id", "away_team", "home_team"]]
emap, used = {}, set()
for i, (a, h, sp, tot, tag, r_sp, r_tot) in enumerate(v.VIEWS):
    hit = games[games.away_team.str.contains(a, regex=False) & games.home_team.str.contains(h, regex=False)]
    if len(hit) != 1:
        raise SystemExit(f"view {a}@{h} matched {len(hit)} games")
    eid = hit.event_id.iloc[0]
    if eid in emap: raise SystemExit(f"two views for {a}@{h}")
    emap[eid] = (sp, tot, tag, r_sp, r_tot)
missing = games[~games.event_id.isin(emap)]
if len(missing): raise SystemExit("games with no view:\n" + missing.to_string())
spread_line = sh[sh.market_key == "spreads"].set_index("event_id")["line"].to_dict()
out = []
for r in sh.itertuples(index=False):
    sp, tot, tag, r_sp, r_tot = emap[r.event_id]
    q = r.q_first
    if r.market_key == "totals":
        p = q + (Phi(tot / v.SIGMA_TOTAL) - 0.5); reason = r_tot
    elif r.market_key == "spreads":
        p = q + (Phi(sp / v.SIGMA_MARGIN) - 0.5); reason = r_sp
    else:  # h2h, home first; same direction as the spread view
        mu = -spread_line[r.event_id] if r.event_id in spread_line else None
        if mu is None:
            from statistics import NormalDist
            mu = NormalDist().inv_cdf(min(max(q, 1e-4), 1 - 1e-4)) * v.SIGMA_MARGIN
        p = q + (Phi((mu + sp) / v.SIGMA_MARGIN) - Phi(mu / v.SIGMA_MARGIN)); reason = r_sp
    p = min(max(p, L.P_MIN), L.P_MAX)
    out.append({"event_id": r.event_id, "market_key": r.market_key, "player_name": "", "line": r.line,
                "away_team": r.away_team, "home_team": r.home_team, "q_first": round(q, 4),
                "p_first": round(p, 4), "tag": tag, "reason": reason})
f = pd.DataFrame(out)
f.to_csv(out_csv, index=False)
f["gap"] = f.p_first - f.q_first
print(f"{len(f)} lines, {f.event_id.nunique()} games; sheet rows {len(sh)}; |gap| mean {f.gap.abs().mean():.3f} max {f.gap.abs().max():.3f}; gap==0: {(f.gap.abs()<1e-4).sum()}")
print(f.market_key.value_counts().to_dict())
