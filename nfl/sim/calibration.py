#!/usr/bin/env python3
"""
NFL Sim Phase 3 — Calibration, K2, K4, and holdout scoring.

2021-2024 ONLY for fitting. 2025 scored once. Raises on season >= 2025
in any fitting function.
"""

import json, time, subprocess
from pathlib import Path

import numpy as np
import pandas as pd
from nfl.sim.seed_util import stable_seed
from sklearn.isotonic import IsotonicRegression

from nfl.sim.engine import _load_tables, _load_ratings
from nfl.sim.anchor import anchor_game, estimate_jacobian, run_anchored_chunked
from nfl.sim.pricer import price_game
from nfl.sim.actuals import actual_player_game_stats

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_DIR = ROOT / "nfl" / "data" / "sim" / "outputs"
LOCK_PATH = ROOT / "research" / "nfl_sim" / "HOLDOUT_2025_SCORED.lock"


def _check_season_guard(seasons, context="fitting"):
    for s in seasons:
        if s >= 2025:
            raise RuntimeError(f"FATAL: {context} has season {s} >= 2025")


def _load_games(seasons):
    """Load game list with market lines from PBP."""
    frames = []
    for s in seasons:
        p = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
        if not p.exists():
            continue
        df = pd.read_parquet(p, columns=["game_id", "season", "week", "home_team",
                                          "away_team", "home_score", "away_score",
                                          "spread_line", "total_line"])
        g = df.drop_duplicates("game_id")
        g = g[g["week"] <= 18]
        frames.append(g)
    return pd.concat(frames, ignore_index=True)


def run_anchored_backtest(seasons, n_sims=1000, J_inv=None):
    """Run anchored sims for all games. Returns list of result dicts."""
    _check_season_guard(seasons, "anchored_backtest") if max(seasons) <= 2024 else None

    _load_tables()
    team_r, tend, sit, kicker, league = _load_ratings()
    pu = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet")
    au = pd.read_parquet(ROOT / "nfl" / "data" / "sim" / "ratings" / "active_universe_weekly.parquet")
    kw = dict(team_r=team_r, tend=tend, sit=sit, kicker=kicker, league=league,
              player_usage=pu, active_uni=au)

    games = _load_games(seasons)
    print(f"Anchored backtest: {len(games)} games, N={n_sims}")

    results = []
    for s in sorted(games["season"].unique()):
        sg = games[games["season"] == s]
        t0 = time.time()
        for _, g in sg.iterrows():
            spread = g["spread_line"]
            total = g["total_line"]
            if pd.isna(spread) or pd.isna(total):
                continue
            seed = stable_seed((g["game_id"], 42))
            r = anchor_game(
                g["home_team"], g["away_team"], s, int(g["week"]),
                spread, total, n_sims=n_sims, seed=seed,
                J_inv=J_inv, with_players=True, **kw)
            r["game_id"] = g["game_id"]
            r["season"] = s
            r["week"] = int(g["week"])
            r["home_team"] = g["home_team"]
            r["away_team"] = g["away_team"]
            r["actual_home"] = g["home_score"]
            r["actual_away"] = g["away_score"]
            r["spread_line"] = spread
            r["total_line"] = total
            results.append(r)
        dt = time.time() - t0
        print(f"  Season {s}: {len(sg)} games, {dt:.0f}s ({dt/len(sg):.1f}s/game)")

    return results


def _crps_sample(samples, observed):
    """CRPS of a sample distribution vs a scalar observation.

    CRPS = E|S - y| - 0.5 * E|S_i - S_j|
    The pairwise term np.mean(|S_i - S_j|) is already the double-mean
    over all i,j pairs, so no additional /n.
    """
    s = np.sort(samples)
    crps = np.mean(np.abs(s - observed)) - 0.5 * np.mean(np.abs(
        s[:, None] - s[None, :]))
    return crps


def score_k2(results):
    """K2: CRPS of anchored sim distribution vs realised, vs naive Normal."""
    rows = []
    for r in results:
        td = r["team_df"]
        margin = (td["home_score"] - td["away_score"]).values.astype(float)
        total = (td["home_score"] + td["away_score"]).values.astype(float)
        actual_margin = r["actual_home"] - r["actual_away"]
        actual_total = r["actual_home"] + r["actual_away"]
        spread = r["spread_line"]
        total_line = r["total_line"]

        crps_margin = _crps_sample(margin, actual_margin)
        crps_total = _crps_sample(total, actual_total)

        rows.append({
            "game_id": r["game_id"], "season": r["season"], "week": r["week"],
            "crps_margin": crps_margin, "crps_total": crps_total,
            "actual_margin": actual_margin, "actual_total": actual_total,
            "sim_mean_margin": margin.mean(), "sim_mean_total": total.mean(),
            "spread_line": spread, "total_line": total_line,
            "converged": r["converged"],
            "home_team": r["home_team"], "away_team": r["away_team"],
            "p_home_cover": (margin + spread > 0).mean(),
            "actual_home_cover": int(actual_margin + spread > 0),
            "p_over": (total > total_line).mean(),
            "actual_over": int(actual_total > total_line),
            "p_home_win": (margin > 0).mean(),
            "actual_home_win": int(actual_margin > 0),
        })

    df = pd.DataFrame(rows)

    # Naive baselines
    # Historical residual SD: margin ~14.2, total ~13.6
    margin_resid = df["actual_margin"] - (-df["spread_line"])
    total_resid = df["actual_total"] - df["total_line"]
    sigma_margin = margin_resid.std()
    sigma_total = total_resid.std()

    # Naive CRPS = sigma * (1/sqrt(pi) + z*Phi(z) + phi(z) - 0.5/sqrt(pi))
    # For Normal(mu, sigma), CRPS = sigma * [z*(2*Phi(z)-1) + 2*phi(z) - 1/sqrt(pi)]
    # where z = (observed - mu) / sigma
    from scipy.stats import norm
    z_margin = (df["actual_margin"] - (-df["spread_line"])) / sigma_margin
    naive_crps_margin = sigma_margin * (z_margin * (2 * norm.cdf(z_margin) - 1) +
                                         2 * norm.pdf(z_margin) - 1 / np.sqrt(np.pi))
    z_total = (df["actual_total"] - df["total_line"]) / sigma_total
    naive_crps_total = sigma_total * (z_total * (2 * norm.cdf(z_total) - 1) +
                                       2 * norm.pdf(z_total) - 1 / np.sqrt(np.pi))

    df["naive_crps_margin"] = naive_crps_margin
    df["naive_crps_total"] = naive_crps_total

    return df


def score_k1_post_anchoring(results):
    """Re-report K1 lines on the ANCHORED sims."""
    all_h, all_a, all_margin = [], [], []
    for r in results:
        td = r["team_df"]
        all_h.extend(td["home_score"].values)
        all_a.extend(td["away_score"].values)
        all_margin.extend((td["home_score"] - td["away_score"]).values)

    pts_team = (np.mean(all_h) + np.mean(all_a)) / 2
    margin_arr = np.array(all_margin)
    abs_margin = np.abs(margin_arr)
    sd_margin = margin_arr.std()

    lines = {
        "pts_team": pts_team,
        "sd_margin_pooled": sd_margin,
        "p_margin_3": (abs_margin == 3).mean() * 100,
        "p_margin_6": (abs_margin == 6).mean() * 100,
        "p_margin_7": (abs_margin == 7).mean() * 100,
    }
    return lines


def fit_calibration_maps(results):
    """Fit isotonic regression maps on 2021-2024.

    Returns dict of family -> {x: [], y: [], n: int}.
    """
    seasons = set(r["season"] for r in results)
    _check_season_guard(seasons, "fit_calibration_maps")

    # Collect prop predictions vs actuals
    prop_data = []
    game_data = []

    for r in results:
        td = r["team_df"]
        N = len(td)
        actual_margin = r["actual_home"] - r["actual_away"]
        actual_total = r["actual_home"] + r["actual_away"]

        margin = td["home_score"].values - td["away_score"].values
        total = td["home_score"].values + td["away_score"].values

        # Spread coverage for various lines
        for sp in np.arange(-14, 14.5, 0.5):
            p = (margin + sp > 0).mean()
            hit = int(actual_margin + sp > 0)
            game_data.append({"family": "margin_side", "pred": p, "hit": hit})

        # Total over/under
        for off in np.arange(-5, 5.5, 0.5):
            line = r["total_line"] + off
            p = (total > line).mean()
            hit = int(actual_total > line)
            game_data.append({"family": "total_side", "pred": p, "hit": hit})

        # Team totals
        for team_score, label in [(td["home_score"].values, "team_total"),
                                   (td["away_score"].values, "team_total")]:
            actual_ts = r["actual_home"] if label == "team_total" and np.array_equal(team_score, td["home_score"].values) else r["actual_away"]
            for line in np.arange(10, 40, 0.5):
                p = (team_score > line).mean()
                hit = int(actual_ts > line)
                game_data.append({"family": "team_total", "pred": p, "hit": hit})

        # Player props
        if r.get("player_df") is not None and len(r["player_df"]) > 0:
            pdf = r["player_df"]
            _score_player_props(pdf, r, prop_data)

    # Fit isotonic for each family
    gdf = pd.DataFrame(game_data)
    cal_maps = {}

    for family in gdf["family"].unique():
        fd = gdf[gdf["family"] == family]
        fd = fd[(fd["pred"] > 0.02) & (fd["pred"] < 0.98)]
        if len(fd) < 100:
            continue
        ir = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
        ir.fit(fd["pred"], fd["hit"])
        xs = np.linspace(0.01, 0.99, 200)
        ys = ir.predict(xs)
        cal_maps[family] = {"x": xs.tolist(), "y": ys.tolist(), "n": len(fd)}

    # Prop calibration maps
    if prop_data:
        pdf_all = pd.DataFrame(prop_data)
        for family in pdf_all["family"].unique():
            fd = pdf_all[pdf_all["family"] == family]
            fd = fd[(fd["pred"] > 0.02) & (fd["pred"] < 0.98)]
            if len(fd) < 50:
                continue
            ir = IsotonicRegression(y_min=0.01, y_max=0.99, out_of_bounds="clip")
            ir.fit(fd["pred"], fd["hit"])
            xs = np.linspace(0.01, 0.99, 200)
            ys = ir.predict(xs)
            cal_maps[family] = {"x": xs.tolist(), "y": ys.tolist(), "n": len(fd)}

    return cal_maps


def actual_player_stats(game_pbp):
    """Wrapper: delegates to actuals.actual_player_game_stats.

    Returns (rec_stats, rush_stats, td_stats) — the 3-tuple callers expect.
    The 4th element (pass_stats) is available from actual_player_game_stats directly.
    """
    rec, rush, td, _pass = actual_player_game_stats(game_pbp)
    return rec, rush, td


def _score_player_props(pdf, game_result, prop_data):
    """Score player props against actual PBP data."""
    s = game_result["season"]
    gid = game_result["game_id"]

    pbp_path = ROOT / "nfl" / "data" / "pbp" / f"pbp_{s}.parquet"
    if not pbp_path.exists():
        return

    pbp = pd.read_parquet(pbp_path)
    game_pbp = pbp[pbp["game_id"] == gid]

    rec_stats, rush_stats, td_stats = actual_player_stats(game_pbp)

    N = pdf["sim_id"].max() + 1 if len(pdf) > 0 else 1000

    # Score props for top players
    pmeans = pdf.groupby(["player_id", "position"]).agg(
        mean_tgt=("targets", "mean")).reset_index()
    top_players = pmeans.nlargest(10, "mean_tgt")["player_id"].values

    for pid in top_players:
        psims = pdf[pdf["player_id"] == pid]
        pos = psims["position"].iloc[0] if len(psims) else "WR"

        stats = pd.DataFrame({"sim_id": np.arange(N)}).merge(
            psims[["sim_id", "receptions", "rec_yds", "rush_yds", "anytime_td"]],
            on="sim_id", how="left").fillna(0)

        ar = rec_stats[rec_stats["player_id"] == pid]
        actual_rec = int(ar["actual_rec"].iloc[0]) if len(ar) else 0
        actual_ry = int(ar["actual_rec_yds"].iloc[0]) if len(ar) else 0

        arush = rush_stats[rush_stats["player_id"] == pid]
        actual_rushy = int(arush["actual_rush_yds"].iloc[0]) if len(arush) else 0

        atd_row = td_stats[td_stats["player_id"] == pid]
        actual_atd = 1 if len(atd_row) > 0 else 0

        for k in [3, 5, 7]:
            p = (stats["receptions"] >= k).mean()
            hit = int(actual_rec >= k)
            prop_data.append({"family": f"prop_rec_{pos}", "pred": p, "hit": hit})

        for y in [20, 40, 60, 80, 100]:
            p = (stats["rec_yds"] >= y).mean()
            hit = int(actual_ry >= y)
            prop_data.append({"family": f"prop_rec_yds_{pos}", "pred": p, "hit": hit})

        for y in [20, 40, 60, 80]:
            p = (stats["rush_yds"] >= y).mean()
            hit = int(actual_rushy >= y)
            prop_data.append({"family": f"prop_rush_yds_{pos}", "pred": p, "hit": hit})

        p_atd = (stats["anytime_td"] >= 1).mean()
        prop_data.append({"family": f"prop_atd_{pos}", "pred": p_atd, "hit": actual_atd})


# ─────────────────────────────────────────────────────────────────────────────
# D72: engine fingerprint + calibration stamp
#
# The stamp answers one question: are these maps valid for the sim that is
# about to run? It is a CONTENT hash, not a git commit, for two reasons.
#   1. HEAD moves every 30 minutes from the Mac dashboard auto-committer. A
#      HEAD comparison goes red within half an hour of every re-fit, on commits
#      that never touched the engine, and a gate that is always red gets ignored.
#   2. A git comparison cannot see UNCOMMITTED edits. fit_5d1 was produced by a
#      run_fit.py that was uncommitted at the time; a commit-based stamp would
#      have recorded a hash that did not describe the code that ran.
#
# Boundary, chosen deliberately: the fingerprint covers what determines the raw
# simulated distribution — the engine, the anchoring, the fitted parameters, and
# every table the engine reads. It does NOT cover nfl/sim/pricer.py. The raking
# and SGP code there does not change a leg's marginal probability, and folding it
# in would fire the gate after a raking-only fix, which is the spurious-red
# failure this decision exists to prevent. If price_game's LEG CONSTRUCTION ever
# changes, add it here and say so.
ENGINE_FINGERPRINT_FILES = [
    ROOT / "nfl" / "sim" / "engine.py",
    ROOT / "nfl" / "sim" / "anchor.py",
    ROOT / "nfl" / "sim" / "params_v1.json",
]
ENGINE_TABLES_DIR = ROOT / "nfl" / "data" / "sim" / "tables"
USAGE_PATH = ROOT / "nfl" / "data" / "sim" / "ratings" / "player_usage_weekly.parquet"

# D81: every season-keyed ratings artifact the engine reads, not just usage.
# ChatGPT audit #3 showed the D77 fingerprint covered usage alone: removing a
# player from a HISTORICAL active lineup, and altering HISTORICAL team passing EPA,
# both changed the simulated sample while the gate stayed green. Each of these is
# hashed over the fit window only, for the D77 reason — 2026 rows cannot affect a
# 2021-2024 fit and must not redden the gate.
RATINGS_DIR = ROOT / "nfl" / "data" / "sim" / "ratings"
FIT_INPUT_FILES = [
    "player_usage_weekly.parquet",
    "active_universe_weekly.parquet",
    "team_ratings_weekly.parquet",
    "tendencies_weekly.parquet",
    "tendencies_situational_weekly.parquet",
    "qb_ratings_weekly.parquet",
    "kicker_weekly.parquet",
    "league_baselines.parquet",
]


def engine_fingerprint():
    """sha256[:16] over the files that determine the simulated distribution.

    Raises if an input is missing — a fingerprint computed over a partial set
    would silently compare equal across a real change.
    """
    import hashlib
    h = hashlib.sha256()
    files = list(ENGINE_FINGERPRINT_FILES)
    if not ENGINE_TABLES_DIR.is_dir():
        raise FileNotFoundError(f"engine tables dir missing: {ENGINE_TABLES_DIR}")
    files += sorted(p for p in ENGINE_TABLES_DIR.iterdir() if p.is_file())
    for f in files:
        if not f.exists():
            raise FileNotFoundError(f"engine fingerprint input missing: {f}")
        h.update(f.name.encode())
        h.update(b"\x00")
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


# D77: the fingerprint covers ONLY the seasons the maps were fitted on.
# Hashing the whole file made every routine data refresh red the gate: the maps
# are fitted on 2021-2024, so 2026 roster churn cannot affect them, yet a 2026-only
# refresh changed the whole-file hash. Verified 2026-09-19: after refreshing the
# nflverse inputs and rebuilding usage, the 2021-2024 block was BIT-IDENTICAL
# (36,273 usage rows, 57,261 active-universe rows, full-frame .equals() True) while
# the whole-file hash moved. A gate that reds on data that cannot affect the fit is
# the same spurious-red failure D72 exists to prevent.
#
# Residual assumption, unchanged by this and still open: maps fitted on 2021-2024
# are assumed to transfer to the live season. This narrowing does not address that;
# it only stops the gate firing on data outside the fit window.
FIT_SEASONS_DEFAULT = [2021, 2022, 2023, 2024]


def usage_fingerprint(fit_seasons=None):
    """sha256[:16] of the FIT-WINDOW rows of the usage table.

    Deterministic across rebuilds: rows are sorted on a stable key and the frame
    is hashed column-wise, so parquet-level encoding differences do not move it.
    """
    import hashlib
    import pandas as pd
    if not USAGE_PATH.exists():
        return None
    seasons = list(fit_seasons or FIT_SEASONS_DEFAULT)
    h = hashlib.sha256()
    h.update(",".join(map(str, seasons)).encode())
    for fname in FIT_INPUT_FILES:          # D81: all fit inputs, not usage alone
        fpath = RATINGS_DIR / fname
        h.update(fname.encode())
        if not fpath.exists():
            raise FileNotFoundError(f"fit input missing: {fpath}")
        df = pd.read_parquet(fpath)
        if "season" in df.columns:
            df = df[df["season"].isin(seasons)]   # fit window only (D77)
        key = [c for c in ("season", "week", "team", "player_id") if c in df.columns]
        if key:
            df = df.sort_values(key)
        df = df.reset_index(drop=True)
        for c in sorted(df.columns):
            h.update(c.encode())
            h.update(pd.util.hash_pandas_object(df[c], index=False).values.tobytes())
    return h.hexdigest()[:16]


def save_calibration(cal_maps, path=None, fit_dir=None, fit_n_games=None,
                     unconverged_share=None, anchor=None):
    """Save calibration maps WITH the full stamp the metadata gate reads.

    D72: the stamp used to be written by hand — no committed code produced
    engine_commit / usage_file_sha256 / fit_dir, so a re-fit could not
    reproduce it. This is now the writer. Keys not passed are preserved from
    the existing file rather than dropped, so a partial call cannot silently
    strip the anchor block.
    """
    import datetime
    if path is None:
        path = ROOT / "nfl" / "sim" / "calibration_v1.json"

    existing = {}
    if Path(path).exists():
        try:
            with open(path) as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    try:
        sha = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                       cwd=ROOT, text=True).strip()
    except Exception:
        sha = "unknown"

    out = dict(existing)
    out["engine_fingerprint"] = engine_fingerprint()
    out["fit_seasons"] = list(FIT_SEASONS_DEFAULT)
    out["usage_file_sha256"] = usage_fingerprint(out["fit_seasons"])
    out["engine_commit"] = sha          # informational only — NOT gated on
    out["fit_date"] = datetime.date.today().isoformat()
    if fit_dir is not None:
        out["fit_dir"] = fit_dir
    if fit_n_games is not None:
        out["fit_n_games"] = fit_n_games
    if unconverged_share is not None:
        out["unconverged_share"] = unconverged_share
    if anchor is not None:
        out["anchor"] = anchor
    out.pop("git_sha", None)            # superseded by engine_commit
    out["maps"] = dict(cal_maps)

    with open(path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"Saved calibration to {path} "
          f"(engine_fingerprint={out['engine_fingerprint']}, "
          f"usage={out['usage_file_sha256']}, {len(cal_maps)} families)")
    return path


def load_calibration(path=None):
    """Load calibration maps."""
    if path is None:
        path = ROOT / "nfl" / "sim" / "calibration_v1.json"
    with open(path) as f:
        data = json.load(f)
    return data["maps"]


def score_2025_holdout(n_sims=1000, J_inv=None):
    """Score 2025 holdout ONCE. Creates lock file."""
    if LOCK_PATH.exists():
        raise RuntimeError(f"FATAL: 2025 already scored. Lock file: {LOCK_PATH}")

    print("=== SCORING 2025 HOLDOUT (one-time) ===")
    results = run_anchored_backtest([2025], n_sims=n_sims, J_inv=J_inv)
    return results


def create_holdout_lock(cal_path=None):
    """Create lock file after 2025 scoring."""
    import datetime
    if cal_path is None:
        cal_path = ROOT / "nfl" / "sim" / "calibration_v1.json"
    cal_sha = "unknown"
    if cal_path.exists():
        with open(cal_path) as f:
            cal_sha = json.load(f).get("git_sha", "unknown")
    with open(LOCK_PATH, "w") as f:
        f.write(f"timestamp: {datetime.datetime.utcnow().isoformat()}Z\n")
        f.write(f"calibration_v1_sha: {cal_sha}\n")
    print(f"Created lock file: {LOCK_PATH}")


def reliability_table(preds, actuals, n_bins=10):
    """Compute reliability table from predictions vs actuals."""
    df = pd.DataFrame({"pred": preds, "actual": actuals})
    df = df.dropna()
    if len(df) < 20:
        return pd.DataFrame()
    try:
        df["dec"] = pd.qcut(df["pred"], n_bins, labels=False, duplicates="drop")
    except ValueError:
        df["dec"] = pd.cut(df["pred"], 5, labels=False)
    tbl = df.groupby("dec").agg(
        sim_p=("pred", "mean"),
        actual=("actual", "mean"),
        n=("actual", "size"),
    ).reset_index()
    tbl["gap"] = tbl["sim_p"] - tbl["actual"]
    tbl["pass"] = tbl["gap"].abs() <= 0.05
    return tbl
