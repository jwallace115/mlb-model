"""
Phase 2 Composite Test: Continuity-conditioned composites for NCAAF portal shock signal.
Research only — pulls from CFBD API and writes report.
"""

import os
import time
import json
import requests
import numpy as np
from scipy import stats
from collections import defaultdict, Counter

# API setup
API_KEY = "VxpuqPMW/47ICJaR5wgxFmFwxXv6mpE9/jWXXCbucjo0QCer4g9mdb5xskr9NTAf"
BASE = "https://api.collegefootballdata.com"
HEADERS = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
SEASONS = [2022, 2023, 2024, 2025]
DELAY = 0.35


def api_get(endpoint, params=None):
    time.sleep(DELAY)
    url = f"{BASE}{endpoint}"
    r = requests.get(url, headers=HEADERS, params=params or {})
    if r.status_code != 200:
        print(f"  WARN: {endpoint} params={params} -> {r.status_code}")
        return []
    return r.json()


# ============================================================
# DATA PULL
# ============================================================
print("=== Pulling transfer portal data ===")
transfers_all = {}
for yr in SEASONS:
    data = api_get("/player/portal", {"year": yr})
    transfers_all[yr] = data
    print(f"  {yr}: {len(data)} transfers")

print("\n=== Pulling games (FBS only via classification filter) ===")
games_all = {}
for yr in SEASONS:
    data = api_get("/games", {"year": yr, "seasonType": "regular", "division": "fbs"})
    # Filter to FBS only using classification
    fbs = [g for g in data if g.get("homeClassification") == "fbs" or g.get("awayClassification") == "fbs"]
    games_all[yr] = fbs
    print(f"  {yr}: {len(fbs)} FBS games (of {len(data)} total)")

print("\n=== Pulling lines ===")
lines_all = {}
for yr in SEASONS:
    data = api_get("/lines", {"year": yr})
    lines_all[yr] = data
    print(f"  {yr}: {len(data)} line entries")

print("\n=== Pulling returning production ===")
returning_all = {}
for yr in SEASONS:
    data = api_get("/player/returning", {"year": yr})
    returning_all[yr] = data
    print(f"  {yr}: {len(data)} teams")

print("\n=== Pulling coaches ===")
coaches_all = {}
for yr in [2021] + SEASONS:
    data = api_get("/coaches", {"year": yr})
    coaches_all[yr] = data
    print(f"  {yr}: {len(data)} coach records")

# ============================================================
# BUILD TEAM-SEASON METRICS
# ============================================================
print("\n=== Building team-season metrics ===")


def get_head_coach(coaches_list, team, year):
    """Find the head coach for a team in a given year."""
    for c in coaches_list:
        for s in c.get("seasons", []):
            if s.get("school") == team and s.get("year") == year:
                return c.get("firstName", "") + " " + c.get("lastName", "")
    return None


# Build portal metrics per team-season
team_metrics = {}  # (team, year) -> dict

for yr in SEASONS:
    transfers = transfers_all[yr]

    # Aggregate portal in/out by team
    portal_in = defaultdict(lambda: {"count": 0, "stars": 0, "positions": []})
    portal_out = defaultdict(lambda: {"count": 0, "stars": 0, "positions": []})

    for t in transfers:
        origin = t.get("origin")
        dest = t.get("destination")
        star = t.get("stars") or 0
        pos = (t.get("position") or "").upper()

        if origin:
            portal_out[origin]["count"] += 1
            portal_out[origin]["stars"] += star
            portal_out[origin]["positions"].append(pos)
        if dest:
            portal_in[dest]["count"] += 1
            portal_in[dest]["stars"] += star
            portal_in[dest]["positions"].append(pos)

    # Collect all FBS teams from games
    fbs_teams = set()
    for g in games_all[yr]:
        if g.get("homeClassification") == "fbs":
            fbs_teams.add(g["homeTeam"])
        if g.get("awayClassification") == "fbs":
            fbs_teams.add(g["awayTeam"])

    for team in fbs_teams:
        in_stars = portal_in[team]["stars"]
        out_stars = portal_out[team]["stars"]
        net = in_stars - out_stars

        # Check if QB left via portal
        qb_positions = {"QB", "DUAL-THREAT QB", "PRO-STYLE QB"}
        qb_out = any(p in qb_positions for p in portal_out[team]["positions"])

        team_metrics[(team, yr)] = {
            "portal_in_stars": in_stars,
            "portal_out_stars": out_stars,
            "net_star_shock": net,
            "portal_in_count": portal_in[team]["count"],
            "portal_out_count": portal_out[team]["count"],
            "qb_in_portal_out": qb_out,
        }

    # Returning production
    for rp in returning_all.get(yr, []):
        team = rp.get("team")
        if not team:
            continue
        pct_ppa = rp.get("percentPPA")
        if (team, yr) in team_metrics:
            team_metrics[(team, yr)]["returning_pct_ppa"] = pct_ppa
        # If team not in metrics yet (no portal activity), skip — they won't be NEGATIVE_SHOCK anyway

    # Coach continuity (compare year vs year-1)
    prior_yr = yr - 1
    for team in fbs_teams:
        if (team, yr) not in team_metrics:
            continue
        hc_current = get_head_coach(coaches_all.get(yr, []), team, yr)
        hc_prior = get_head_coach(coaches_all.get(prior_yr, []), team, prior_yr)
        team_metrics[(team, yr)]["hc_current"] = hc_current
        team_metrics[(team, yr)]["hc_prior"] = hc_prior
        team_metrics[(team, yr)]["coach_continuity"] = (
            hc_current is not None and hc_prior is not None and hc_current == hc_prior
        )

print(f"  Built metrics for {len(team_metrics)} team-seasons")

# Show some stats
has_ret = sum(1 for v in team_metrics.values() if v.get("returning_pct_ppa") is not None)
has_coach = sum(1 for v in team_metrics.values() if v.get("coach_continuity") is not None)
print(f"  With returning production: {has_ret}")
print(f"  With coach continuity data: {has_coach}")

# ============================================================
# COMPUTE NEGATIVE_SHOCK THRESHOLD (bottom quartile)
# ============================================================
all_net = [v["net_star_shock"] for v in team_metrics.values()]
q25 = np.percentile(all_net, 25)
print(f"\n  net_star_shock Q25 = {q25:.1f}")
print(f"  Distribution: min={min(all_net)}, max={max(all_net)}, median={np.median(all_net):.1f}")

for key, val in team_metrics.items():
    val["is_negative_shock"] = val["net_star_shock"] <= q25

neg_shock_teams = [(k, v) for k, v in team_metrics.items() if v["is_negative_shock"]]
print(f"  NEGATIVE_SHOCK teams: {len(neg_shock_teams)}")

# Returning production median among NEGATIVE_SHOCK teams
neg_shock_ret = [v.get("returning_pct_ppa") for _, v in neg_shock_teams
                 if v.get("returning_pct_ppa") is not None]
if neg_shock_ret:
    ret_median = np.median(neg_shock_ret)
    print(f"  Returning PPA median (among NEG_SHOCK with data): {ret_median:.3f} (N={len(neg_shock_ret)})")
else:
    ret_median = 0.5  # fallback
    print(f"  WARN: No returning PPA data among NEG_SHOCK teams, using median=0.5 fallback")

for key, val in team_metrics.items():
    rp = val.get("returning_pct_ppa")
    val["high_returning"] = rp is not None and rp >= ret_median
    val["returning_qb"] = not val.get("qb_in_portal_out", True)

# ============================================================
# BUILD LINES LOOKUP
# ============================================================
print("\n=== Building lines lookup ===")
lines_lookup = {}  # game_id -> spread (home perspective)
for yr in SEASONS:
    for entry in lines_all[yr]:
        gid = entry.get("id")
        best_line = None
        for line in entry.get("lines", []):
            spread = line.get("spread")
            if spread is not None:
                prov = (line.get("provider") or "").lower()
                if best_line is None or "consensus" in prov:
                    best_line = spread
        if best_line is not None:
            lines_lookup[gid] = best_line

print(f"  Lines available for {len(lines_lookup)} games")

# ============================================================
# BUILD GAME-LEVEL OBSERVATIONS
# ============================================================
print("\n=== Building game-level observations ===")
observations = []

for yr in SEASONS:
    matched = 0
    for game in games_all[yr]:
        gid = game.get("id")
        week = game.get("week", 99)
        home = game.get("homeTeam")
        away = game.get("awayTeam")
        hp = game.get("homePoints")
        ap = game.get("awayPoints")
        home_conf = game.get("homeConference", "")
        away_conf = game.get("awayConference", "")

        if hp is None or ap is None:
            continue
        if gid not in lines_lookup:
            continue

        spread = lines_lookup[gid]  # home perspective (neg = home favored)
        home_margin = hp - ap
        home_ats = home_margin + spread  # ATS for home

        if home_ats == 0:
            continue  # push

        home_cover = home_ats > 0

        home_metrics = team_metrics.get((home, yr), {})
        away_metrics = team_metrics.get((away, yr), {})

        matched += 1

        # Home team observation
        observations.append({
            "game_id": gid,
            "year": yr,
            "week": week,
            "team": home,
            "opponent": away,
            "is_home": True,
            "team_spread": spread,
            "margin": home_margin,
            "ats_margin": home_ats,
            "cover": home_cover,
            "conference": home_conf,
            "is_negative_shock": home_metrics.get("is_negative_shock", False),
            "high_returning": home_metrics.get("high_returning", False),
            "returning_qb": home_metrics.get("returning_qb", False),
            "coach_continuity": home_metrics.get("coach_continuity", False),
            "net_star_shock": home_metrics.get("net_star_shock", 0),
        })

        # Away team observation
        away_ats = -(home_margin + spread)  # = -(home_margin) - spread = away_margin - (-spread)
        # Actually: away_margin = -home_margin, away_spread = -spread
        # away_ats_margin = away_margin + away_spread = -home_margin + (-spread) = -(home_margin + spread) = -home_ats
        if away_ats == 0:
            continue

        observations.append({
            "game_id": gid,
            "year": yr,
            "week": week,
            "team": away,
            "opponent": home,
            "is_home": False,
            "team_spread": -spread,
            "margin": -home_margin,
            "ats_margin": away_ats,
            "cover": away_ats > 0,
            "conference": away_conf,
            "is_negative_shock": away_metrics.get("is_negative_shock", False),
            "high_returning": away_metrics.get("high_returning", False),
            "returning_qb": away_metrics.get("returning_qb", False),
            "coach_continuity": away_metrics.get("coach_continuity", False),
            "net_star_shock": away_metrics.get("net_star_shock", 0),
        })

    print(f"  {yr}: {matched} games with lines matched")

print(f"\n  Total observations: {len(observations)}")

# ============================================================
# FILTER & BUCKET
# ============================================================
early = [o for o in observations if o["week"] <= 4]
print(f"  Weeks 0-4 observations: {len(early)}")
print(f"  Weeks 0-4 NEG_SHOCK: {sum(1 for o in early if o['is_negative_shock'])}")

P5_CONFERENCES = {"SEC", "Big Ten", "Big 12", "ACC", "Pac-12"}


def bucket_filter(obs, bucket_name):
    result = []
    for o in obs:
        neg = o.get("is_negative_shock", False)
        high_ret = o.get("high_returning", False)
        ret_qb = o.get("returning_qb", False)
        coach_cont = o.get("coach_continuity", False)

        if bucket_name == "A":
            if neg: result.append(o)
        elif bucket_name == "B":
            if neg and high_ret: result.append(o)
        elif bucket_name == "C":
            if neg and ret_qb: result.append(o)
        elif bucket_name == "D":
            if neg and coach_cont: result.append(o)
        elif bucket_name == "E":
            if neg and ret_qb and coach_cont: result.append(o)
        elif bucket_name == "F":
            if neg and high_ret and ret_qb: result.append(o)
    return result


def compute_stats(obs_list):
    if not obs_list:
        return {"N": 0, "covers": 0, "cover_pct": 0.0, "mean_ats": 0.0, "p_binom": 1.0}
    n = len(obs_list)
    covers = sum(1 for o in obs_list if o["cover"])
    cover_pct = covers / n * 100
    mean_ats = np.mean([o["ats_margin"] for o in obs_list])
    p_binom = stats.binomtest(covers, n, 0.5).pvalue
    return {"N": n, "covers": covers, "cover_pct": cover_pct, "mean_ats": mean_ats, "p_binom": p_binom}


def by_season(obs_list):
    seasons = sorted(set(o["year"] for o in obs_list))
    return {yr: compute_stats([o for o in obs_list if o["year"] == yr]) for yr in seasons}


# ============================================================
# PHASE 1 — BUCKET RESULTS
# ============================================================
print("\n" + "=" * 60)
print("PHASE 1: COMPOSITE BUCKET RESULTS (Weeks 0-4)")
print("=" * 60)

buckets = ["A", "B", "C", "D", "E", "F"]
bucket_labels = {
    "A": "NEGATIVE_SHOCK (baseline)",
    "B": "NEG_SHOCK + HIGH_RETURNING",
    "C": "NEG_SHOCK + RETURNING_QB",
    "D": "NEG_SHOCK + COACH_CONTINUITY",
    "E": "NEG_SHOCK + RET_QB + COACH_CONT",
    "F": "NEG_SHOCK + HIGH_RET + RET_QB",
}

results = {}
for b in buckets:
    filtered = bucket_filter(early, b)
    s = compute_stats(filtered)
    ss = by_season(filtered)
    results[b] = {"stats": s, "by_season": ss, "obs": filtered}

    print(f"\n{bucket_labels[b]}:")
    print(f"  N={s['N']}, Covers={s['covers']}, Cover%={s['cover_pct']:.1f}%, "
          f"ATS Margin={s['mean_ats']:+.2f}, p={s['p_binom']:.4f}")
    for yr, ys in ss.items():
        print(f"    {yr}: N={ys['N']}, Cover%={ys['cover_pct']:.1f}%, ATS={ys['mean_ats']:+.2f}")

# Best bucket (N >= 50 required)
valid = [b for b in buckets if results[b]["stats"]["N"] >= 50]
if valid:
    best_bucket = max(valid, key=lambda b: results[b]["stats"]["cover_pct"])
else:
    best_bucket = max(buckets, key=lambda b: results[b]["stats"]["N"])
print(f"\n>>> Best bucket: {bucket_labels[best_bucket]} "
      f"({results[best_bucket]['stats']['cover_pct']:.1f}% cover, N={results[best_bucket]['stats']['N']})")

# Week 0 excluded
print("\n--- Week 0 excluded (Weeks 1-4 only) ---")
early_no_w0 = [o for o in early if o["week"] >= 1]
for b in buckets:
    filtered = bucket_filter(early_no_w0, b)
    s = compute_stats(filtered)
    print(f"  {bucket_labels[b]}: N={s['N']}, Cover%={s['cover_pct']:.1f}%, ATS={s['mean_ats']:+.2f}")

# ============================================================
# PHASE 2 — FAVORITE VS UNDERDOG
# ============================================================
print("\n" + "=" * 60)
print("PHASE 2: FAVORITE VS UNDERDOG (best composite)")
print("=" * 60)

best_obs = results[best_bucket]["obs"]
favs = [o for o in best_obs if o["team_spread"] < 0]
dogs = [o for o in best_obs if o["team_spread"] > 0]

sf = compute_stats(favs)
sd = compute_stats(dogs)
print(f"  Favorites: N={sf['N']}, Cover%={sf['cover_pct']:.1f}%, ATS={sf['mean_ats']:+.2f}, p={sf['p_binom']:.4f}")
print(f"  Underdogs: N={sd['N']}, Cover%={sd['cover_pct']:.1f}%, ATS={sd['mean_ats']:+.2f}, p={sd['p_binom']:.4f}")

# ============================================================
# PHASE 3 — CONFERENCE TIER
# ============================================================
print("\n" + "=" * 60)
print("PHASE 3: CONFERENCE TIER (best composite)")
print("=" * 60)

p5_obs = [o for o in best_obs if o.get("conference") in P5_CONFERENCES]
g5_obs = [o for o in best_obs if o.get("conference") and o.get("conference") not in P5_CONFERENCES]

sp5 = compute_stats(p5_obs)
sg5 = compute_stats(g5_obs)
print(f"  P5/P4: N={sp5['N']}, Cover%={sp5['cover_pct']:.1f}%, ATS={sp5['mean_ats']:+.2f}")
print(f"  G5: N={sg5['N']}, Cover%={sg5['cover_pct']:.1f}%, ATS={sg5['mean_ats']:+.2f}")

# ============================================================
# PHASE 4 — SPREAD BANDS
# ============================================================
print("\n" + "=" * 60)
print("PHASE 4: SPREAD BANDS (best composite)")
print("=" * 60)

bands = [
    ("< 3", lambda o: abs(o["team_spread"]) < 3),
    ("3-7", lambda o: 3 <= abs(o["team_spread"]) < 7),
    ("7-14", lambda o: 7 <= abs(o["team_spread"]) < 14),
    ("14+", lambda o: abs(o["team_spread"]) >= 14),
]
for label, filt in bands:
    sub = [o for o in best_obs if filt(o)]
    sb = compute_stats(sub)
    print(f"  |spread| {label}: N={sb['N']}, Cover%={sb['cover_pct']:.1f}%, ATS={sb['mean_ats']:+.2f}")

# ============================================================
# PHASE 5 — FADE CURVE
# ============================================================
print("\n" + "=" * 60)
print("PHASE 5: FADE CURVE (best composite, all weeks)")
print("=" * 60)

all_best = bucket_filter(observations, best_bucket)
windows = [
    ("Weeks 0-2", lambda o: o["week"] <= 2),
    ("Weeks 3-4", lambda o: 3 <= o["week"] <= 4),
    ("Weeks 5-8", lambda o: 5 <= o["week"] <= 8),
    ("Weeks 9+", lambda o: o["week"] >= 9),
]
for label, filt in windows:
    sub = [o for o in all_best if filt(o)]
    sw = compute_stats(sub)
    print(f"  {label}: N={sw['N']}, Cover%={sw['cover_pct']:.1f}%, ATS={sw['mean_ats']:+.2f}")

# ============================================================
# PHASE 6 — ROBUSTNESS
# ============================================================
print("\n" + "=" * 60)
print("PHASE 6: ROBUSTNESS CHECKS")
print("=" * 60)

# 6a: Remove top 5 most frequent teams
team_counts = Counter(o["team"] for o in best_obs)
top5 = [t for t, _ in team_counts.most_common(5)]
print(f"\n  Top 5 teams: {top5}")
for t, c in team_counts.most_common(5):
    sub_t = [o for o in best_obs if o["team"] == t]
    st = compute_stats(sub_t)
    print(f"    {t}: N={c}, Cover%={st['cover_pct']:.1f}%")

excluded = [o for o in best_obs if o["team"] not in top5]
se = compute_stats(excluded)
print(f"  Excluding top 5: N={se['N']}, Cover%={se['cover_pct']:.1f}%, ATS={se['mean_ats']:+.2f}")

# 6b: Season dominance
print("\n  Season stability:")
bss = results[best_bucket]["by_season"]
total_covers = results[best_bucket]["stats"]["covers"]
for yr, ys in bss.items():
    pct_of_total = ys["covers"] / total_covers * 100 if total_covers > 0 else 0
    print(f"    {yr}: {ys['covers']} covers ({pct_of_total:.0f}% of total), Cover%={ys['cover_pct']:.1f}%")

any_dominant = any(ys["covers"] / total_covers > 0.50 for ys in bss.values()) if total_covers > 0 else False
seasons_above = sum(1 for ys in bss.values() if ys["cover_pct"] > 50 and ys["N"] >= 10)
print(f"    Single season >50% of covers? {'YES' if any_dominant else 'No'}")
print(f"    Seasons above 50% cover (N>=10): {seasons_above}/4")

# 6c: Conference breakdown
print("\n  Conference breakdown:")
conf_counts = Counter(o.get("conference", "Unknown") for o in best_obs)
for conf, cnt in conf_counts.most_common(10):
    sub = [o for o in best_obs if o.get("conference") == conf]
    sc = compute_stats(sub)
    print(f"    {conf}: N={sc['N']}, Cover%={sc['cover_pct']:.1f}%")

total_n = results[best_bucket]["stats"]["N"]
conf_dom = any(cnt / total_n > 0.40 for cnt in conf_counts.values()) if total_n > 0 else False
print(f"    Single conference >40%? {'YES' if conf_dom else 'No'}")

# ============================================================
# ALL BUCKETS EXTENDED SUMMARY
# ============================================================
print("\n" + "=" * 60)
print("ALL BUCKETS: FAV/W0-2 DETAIL")
print("=" * 60)
for b in buckets:
    obs_b = results[b]["obs"]
    if not obs_b:
        continue
    s = results[b]["stats"]
    favs_b = compute_stats([o for o in obs_b if o["team_spread"] < 0])
    w02 = compute_stats([o for o in obs_b if o["week"] <= 2])
    print(f"  {bucket_labels[b]}: All={s['cover_pct']:.1f}%(N={s['N']}), "
          f"Favs={favs_b['cover_pct']:.1f}%(N={favs_b['N']}), "
          f"Wk0-2={w02['cover_pct']:.1f}%(N={w02['N']})")

# ============================================================
# DECISION
# ============================================================
print("\n" + "=" * 60)
print("DECISION")
print("=" * 60)

best_s = results[best_bucket]["stats"]
advance = best_s["cover_pct"] >= 54.5 and best_s["N"] >= 80 and seasons_above >= 3
near_miss = (53.5 <= best_s["cover_pct"] < 54.5) or (best_s["N"] < 80 and best_s["cover_pct"] >= 54.5)

if advance:
    decision = "ADVANCE"
elif near_miss:
    decision = "NEAR MISS"
else:
    decision = "CLOSE"

print(f"  Best composite: {bucket_labels[best_bucket]}")
print(f"  Cover%: {best_s['cover_pct']:.1f}%")
print(f"  N: {best_s['N']}")
print(f"  p-value: {best_s['p_binom']:.4f}")
print(f"  Seasons >= 50% cover: {seasons_above}/4")
print(f"  Robustness (excl top 5): {se['cover_pct']:.1f}%")
print(f"  Decision: {decision}")

# Also check: second-best bucket that might be better for certain criteria
for b in buckets:
    s = results[b]["stats"]
    if s["N"] >= 80 and s["cover_pct"] >= 54.5:
        bss_b = results[b]["by_season"]
        sa_b = sum(1 for ys in bss_b.values() if ys["cover_pct"] > 50 and ys["N"] >= 10)
        print(f"  Also qualifies: {bucket_labels[b]} ({s['cover_pct']:.1f}%, N={s['N']}, {sa_b}/4 seasons)")

# ============================================================
# SAVE DATA FOR REPORT
# ============================================================
report_data = {
    "best_bucket": best_bucket,
    "best_label": bucket_labels[best_bucket],
    "decision": decision,
    "q25_threshold": float(q25),
    "ret_median": float(ret_median),
    "n_team_seasons": len(team_metrics),
    "n_observations": len(observations),
    "n_early": len(early),
}

# Bucket results
for b in buckets:
    s = results[b]["stats"]
    ss = results[b]["by_season"]
    obs_b = results[b]["obs"]
    report_data[f"bucket_{b}"] = {
        "label": bucket_labels[b],
        "N": s["N"], "covers": s["covers"], "cover_pct": round(s["cover_pct"], 1),
        "mean_ats": round(s["mean_ats"], 2), "p_binom": round(s["p_binom"], 4),
        "by_season": {str(yr): {"N": ys["N"], "cover_pct": round(ys["cover_pct"], 1),
                                "mean_ats": round(ys["mean_ats"], 2)}
                     for yr, ys in ss.items()},
    }

with open("/Users/jw115/mlb-model/research/ncaaf_portal/phase2_data.json", "w") as f:
    json.dump(report_data, f, indent=2)

print("\n=== Done. Data saved. ===")
