#!/usr/bin/env python3
"""
LM-1b: Grade all six cells from the frozen registry.

CLV scale (LM-D4): clv_pp = Pinnacle de-vigged close − HR RAW implied prob (paid price).
drift_pp = Pinnacle de-vigged close − HR de-vigged prob (close-vs-fair comparison).
clv_cents = American-odds-derived edge in cents per dollar.
clv_valid = True only when close point == bet point (spreads/totals) or market is h2h.

C5 direction (LM-D4): fire only when public side is overtaxed (gap > 0 for fav/Over).
C5-bidirectional reported separately, not graded against the bar.
"""

import sys, time
from pathlib import Path
from datetime import datetime, timezone

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

TAPE_DIR = ROOT / "research" / "line_movement" / "tape"
OUT_DIR = ROOT / "research" / "line_movement"


def american_to_implied(price):
    if pd.isna(price):
        return np.nan
    if price > 0:
        return 100.0 / (price + 100.0)
    return abs(price) / (abs(price) + 100.0)


def american_to_decimal(price):
    """American odds to decimal payout per $1 staked."""
    if pd.isna(price):
        return np.nan
    if price > 0:
        return 1.0 + price / 100.0
    return 1.0 + 100.0 / abs(price)


def _ts_utc(v):
    t = pd.Timestamp(v)
    return t.tz_localize("UTC") if t.tzinfo is None else t


def wilson_ci(hits, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 1.0
    p_hat = hits / n
    denom = 1 + z**2 / n
    centre = (p_hat + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p_hat * (1 - p_hat) + z**2 / (4 * n)) / n) / denom
    return p_hat, max(0, centre - margin), min(1, centre + margin)


def permutation_null(values, n_draws=1000, seed=42):
    rng = np.random.RandomState(seed)
    null_means = [np.mean(values * rng.choice([-1, 1], size=len(values)))
                  for _ in range(n_draws)]
    return np.mean(null_means), np.std(null_means)


def compute_ats_outcome(market, side_outcome, point_taken, home_score, away_score,
                        home_team, away_team):
    if pd.isna(home_score) or pd.isna(away_score):
        return np.nan
    home_score, away_score = float(home_score), float(away_score)
    if market == "spreads":
        if side_outcome == home_team:
            margin = (home_score - away_score) + point_taken
        else:
            margin = (away_score - home_score) + point_taken
    elif market == "totals":
        total = home_score + away_score
        margin = (total - point_taken) if side_outcome == "Over" else (point_taken - total)
    elif market == "h2h":
        if side_outcome == home_team:
            margin = home_score - away_score
        else:
            margin = away_score - home_score
    else:
        return np.nan
    if margin > 0:
        return "hit"
    elif margin < 0:
        return "miss"
    return "push"


# ---- data loading ----

def load_tape():
    tape = pd.read_parquet(TAPE_DIR / "lm_tape_2026.parquet")
    tape["snapshot_utc"] = pd.to_datetime(tape["snapshot_utc"], utc=True)
    tape["commence_time"] = pd.to_datetime(tape["commence_time"], utc=True)
    return tape


def load_events():
    ev = pd.read_parquet(TAPE_DIR / "lm_events_2026.parquet")
    ev["commence_time"] = pd.to_datetime(ev["commence_time"], utc=True)
    return ev


# ---- CLV helpers ----

def get_pinn_close(tape, event_id, market, outcome):
    """Return (devig_prob, point) for Pinnacle close."""
    pinn = tape[(tape["event_id"] == event_id) &
                (tape["market"] == market) &
                (tape["bookmaker"] == "pinnacle") &
                (tape["outcome_name"] == outcome)]
    if len(pinn) == 0:
        return np.nan, np.nan
    kick = pinn["commence_time"].iloc[0]
    close_cutoff = kick - pd.Timedelta(minutes=60)
    cc = pinn[pinn["snapshot_utc"] <= close_cutoff]
    row = cc.iloc[-1] if len(cc) > 0 else pinn.iloc[-1]
    return row["devig_prob"], row["point"]


def get_hr_at_snap(tape, event_id, market, outcome, at_or_after_snap, hr_book):
    """Return dict with HR snapshot data, or None."""
    hr = tape[(tape["event_id"] == event_id) &
              (tape["market"] == market) &
              (tape["bookmaker"] == hr_book) &
              (tape["outcome_name"] == outcome) &
              (tape["snapshot_utc"] >= at_or_after_snap)]
    if len(hr) == 0:
        return None
    row = hr.iloc[0]
    return {"snapshot_utc": row["snapshot_utc"],
            "point": row["point"],
            "price": row["price"],
            "raw_implied": row["raw_implied"],
            "devig_prob": row["devig_prob"]}


def build_bet_row(cell, sport, eid, mkt, bet_outcome, timing, snap, hr, ev,
                  tape, extra=None):
    """Construct a single bet dict with all CLV columns."""
    hr_book_name = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"
    home, away = ev["home_team"], ev["away_team"]

    pinn_close_devig, pinn_close_pt = get_pinn_close(tape, eid, mkt, bet_outcome)

    hr_raw = hr["raw_implied"]   # RAW implied (with vig)
    hr_dev = hr["devig_prob"]     # de-vigged

    # CLV (paid-price scale): fair close − raw paid
    clv_pp = (pinn_close_devig - hr_raw) * 100 if not pd.isna(pinn_close_devig) else np.nan

    # drift_pp (fair-vs-fair): close devig − bet devig
    drift_pp = (pinn_close_devig - hr_dev) * 100 if not pd.isna(pinn_close_devig) else np.nan

    # clv_cents: decimal-odds edge per dollar
    # Edge = (fair_prob × decimal_payout) − 1, where fair_prob = pinn_close_devig
    hr_decimal = american_to_decimal(hr["price"])
    clv_cents = (pinn_close_devig * hr_decimal - 1.0) * 100 if (
        not pd.isna(pinn_close_devig) and not pd.isna(hr_decimal)) else np.nan

    # Comparability gate
    if mkt == "h2h":
        clv_valid = True
        clv_reason = ""
    elif pd.isna(pinn_close_pt) or pd.isna(hr["point"]):
        clv_valid = False
        clv_reason = "missing_point"
    elif hr["point"] == pinn_close_pt:
        clv_valid = True
        clv_reason = ""
    else:
        clv_valid = False
        clv_reason = f"point_mismatch:{hr['point']}vs{pinn_close_pt}"

    ats = compute_ats_outcome(mkt, bet_outcome, hr["point"],
                              ev["home_score"], ev["away_score"], home, away)

    row = {
        "cell": cell,
        "sport": sport,
        "event_id": eid,
        "market": mkt,
        "side": bet_outcome,
        "trigger_snapshot": snap,
        "bet_snapshot": hr["snapshot_utc"],
        "hr_point": hr["point"],
        "hr_price": hr["price"],
        "hr_raw_implied": hr_raw,
        "hr_devig": hr_dev,
        "pinn_close_devig": pinn_close_devig,
        "pinn_close_point": pinn_close_pt,
        "clv_pp": clv_pp,
        "drift_pp": drift_pp,
        "clv_cents": clv_cents,
        "clv_valid": clv_valid,
        "clv_reason": clv_reason,
        "ats_outcome": ats,
        "timing": timing,
        "home_team": home,
        "away_team": away,
        "home_score": ev["home_score"],
        "away_score": ev["away_score"],
    }
    if extra:
        row.update(extra)
    return row


# ---- cell grading functions ----

def grade_c1(tape, events, sport):
    bets = []
    sport_events = events[(events["sport"] == sport) & (events["market"] == "spreads")]
    hr_book = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"

    for _, ev in sport_events.iterrows():
        if not ev["key_crossings_json"]:
            continue
        try:
            crossings = eval(ev["key_crossings_json"])
        except:
            continue
        eid, home, away = ev["event_id"], ev["home_team"], ev["away_team"]

        for cx in crossings:
            new_pt, kn = cx["new_point"], cx["key_number"]
            snap = _ts_utc(cx["snapshot_utc"])

            if abs(new_pt) >= kn:
                bet_outcome = away if new_pt < 0 else home
            else:
                bet_outcome = home if new_pt < 0 else away

            for timing in ["trigger", "next"]:
                search = snap if timing == "trigger" else snap + pd.Timedelta(seconds=1)
                hr = get_hr_at_snap(tape, eid, "spreads", bet_outcome, search, hr_book)
                if hr is None:
                    continue
                bets.append(build_bet_row("C1", sport, eid, "spreads", bet_outcome,
                                          timing, snap, hr, ev, tape,
                                          {"key_number": kn, "prev_point": cx["prev_point"],
                                           "new_point": new_pt}))
    return bets


def grade_c2(tape, events, sport):
    bets = []
    hr_book = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"

    for mkt in ["spreads", "totals"]:
        for _, ev in events[(events["sport"] == sport) & (events["market"] == mkt)].iterrows():
            if not ev["changes_json"] or not ev["hr_lags_json"]:
                continue
            try:
                changes, lags = eval(ev["changes_json"]), eval(ev["hr_lags_json"])
            except:
                continue
            eid, home, away = ev["event_id"], ev["home_team"], ev["away_team"]

            for ch, lag in zip(changes, lags):
                if ch["abs_delta"] < 0.5 or pd.isna(lag) or lag == 0:
                    continue
                snap, delta = _ts_utc(ch["snapshot_utc"]), ch["delta"]
                if mkt == "spreads":
                    bet_outcome = away if delta > 0 else home
                else:
                    bet_outcome = "Over" if delta > 0 else "Under"

                for timing in ["trigger", "next"]:
                    search = snap if timing == "trigger" else snap + pd.Timedelta(seconds=1)
                    hr = get_hr_at_snap(tape, eid, mkt, bet_outcome, search, hr_book)
                    if hr is None:
                        continue
                    bets.append(build_bet_row("C2", sport, eid, mkt, bet_outcome,
                                              timing, snap, hr, ev, tape,
                                              {"lag_snaps": lag, "pinn_delta": delta}))
    return bets


def grade_c3(tape, events, sport):
    bets = []
    hr_book = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"

    for mkt in ["spreads", "totals"]:
        for _, ev in events[(events["sport"] == sport) & (events["market"] == mkt)].iterrows():
            if not ev["early_changes_json"]:
                continue
            try:
                early = eval(ev["early_changes_json"])
            except:
                continue
            eid, home, away = ev["event_id"], ev["home_team"], ev["away_team"]

            for ch in early:
                if ch["abs_delta"] < 1.0:
                    continue
                snap, delta = _ts_utc(ch["snapshot_utc"]), ch["delta"]
                if mkt == "spreads":
                    bet_outcome = home if delta > 0 else away
                else:
                    bet_outcome = "Under" if delta > 0 else "Over"

                for timing in ["trigger", "next"]:
                    search = snap if timing == "trigger" else snap + pd.Timedelta(seconds=1)
                    hr = get_hr_at_snap(tape, eid, mkt, bet_outcome, search, hr_book)
                    if hr is None:
                        continue
                    bets.append(build_bet_row("C3", sport, eid, mkt, bet_outcome,
                                              timing, snap, hr, ev, tape,
                                              {"pinn_delta": delta}))
    return bets


def grade_c4(tape, events, sport):
    bets = []
    hr_book = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"

    for mkt in ["spreads", "totals"]:
        for _, ev in events[(events["sport"] == sport) & (events["market"] == mkt)].iterrows():
            if not ev["reversals_json"]:
                continue
            try:
                reversals = eval(ev["reversals_json"])
            except:
                continue
            eid, home, away = ev["event_id"], ev["home_team"], ev["away_team"]

            for rev in reversals:
                rev_snap = _ts_utc(rev["reversal_snapshot"])
                rev_delta = rev["reversal_delta"]
                if mkt == "spreads":
                    bet_outcome = away if rev_delta > 0 else home
                else:
                    bet_outcome = "Over" if rev_delta > 0 else "Under"

                for timing in ["trigger", "next"]:
                    search = rev_snap if timing == "trigger" else rev_snap + pd.Timedelta(seconds=1)
                    hr = get_hr_at_snap(tape, eid, mkt, bet_outcome, search, hr_book)
                    if hr is None:
                        continue
                    bets.append(build_bet_row("C4", sport, eid, mkt, bet_outcome,
                                              timing, rev_snap, hr, ev, tape,
                                              {"initial_delta": rev["initial_delta"],
                                               "reversal_delta": rev_delta}))
    return bets


def grade_c5(tape, events, sport, registered_only=True):
    """C5: Hard Rock shade.

    registered_only=True: fire only when public side is overtaxed (gap > 0 for fav/Over).
    registered_only=False: bidirectional (LM-1's version).
    """
    cell_label = "C5" if registered_only else "C5-bidir"
    bets = []
    hr_book = "hardrockbet_fl" if sport == "nfl" else "hardrockbet"

    for mkt in ["spreads", "totals", "h2h"]:
        for _, ev in events[(events["sport"] == sport) & (events["market"] == mkt)].iterrows():
            if pd.isna(ev["first_shade_gap_pp"]):
                continue
            eid, home, away = ev["event_id"], ev["home_team"], ev["away_team"]
            shade_snap = _ts_utc(ev["first_shade_snap"])
            gap = ev["first_shade_gap_pp"]

            # Determine public side and whether it is overtaxed
            if mkt == "spreads":
                pinn_open = ev.get("pinn_open_point", np.nan)
                if pd.isna(pinn_open):
                    continue
                # Public side = favourite. Home is fav when spread < 0.
                # gap is measured on home outcome (gap = HR_devig_home - Pinn_devig_home)
                if pinn_open < 0:
                    # Home is fav = public side
                    public_overtaxed = gap > 0  # HR charges more for home
                    bet_outcome = away if gap > 0 else home
                else:
                    # Away is fav = public side
                    # gap < 0 means HR_devig_home < Pinn_devig_home → HR overprices away
                    public_overtaxed = gap < 0
                    bet_outcome = home if gap < 0 else away
            elif mkt == "totals":
                # Public = Over. gap measured on Over (home outcome for totals).
                public_overtaxed = gap > 0
                bet_outcome = "Under" if gap > 0 else "Over"
            elif mkt == "h2h":
                # Public = favourite. gap on home.
                # If home is fav (gap measured on home), gap > 0 → overtaxed
                # Need to know who is fav. Use Pinnacle devig at trigger.
                pinn_open_devig = ev.get("pinn_open_devig_home", np.nan)
                if pd.isna(pinn_open_devig):
                    continue
                if pinn_open_devig > 0.5:
                    # Home is fav
                    public_overtaxed = gap > 0
                    bet_outcome = away if gap > 0 else home
                else:
                    public_overtaxed = gap < 0
                    bet_outcome = home if gap < 0 else away
            else:
                continue

            if registered_only and not public_overtaxed:
                continue

            for timing in ["trigger", "next"]:
                search = shade_snap if timing == "trigger" else shade_snap + pd.Timedelta(seconds=1)
                hr = get_hr_at_snap(tape, eid, mkt, bet_outcome, search, hr_book)
                if hr is None:
                    continue
                bets.append(build_bet_row(cell_label, sport, eid, mkt, bet_outcome,
                                          timing, shade_snap, hr, ev, tape,
                                          {"shade_gap_pp": gap,
                                           "public_overtaxed": public_overtaxed}))
    return bets


def grade_c6(tape, events, sport):
    return []  # No fires — documented in LM-1


# ---- statistics ----

def grade_cell_stats(bets_df, cell, sport, timing="next"):
    subset = bets_df[(bets_df["cell"] == cell) &
                     (bets_df["sport"] == sport) &
                     (bets_df["timing"] == timing)]
    if len(subset) == 0:
        return None

    n_total = len(subset)

    # Only valid CLV rows
    valid = subset[subset["clv_valid"] == True]
    n_excluded = n_total - len(valid)
    valid_clv = valid["clv_pp"].dropna()
    n_clv = len(valid_clv)

    if n_clv > 0:
        mean_clv = valid_clv.mean()
        se_clv = valid_clv.std() / np.sqrt(n_clv) if n_clv > 1 else np.nan
        t_clv = mean_clv / se_clv if se_clv > 0 else np.nan
        null_mean, null_sd = permutation_null(valid_clv.values)
    else:
        mean_clv = se_clv = t_clv = null_mean = null_sd = np.nan

    # drift_pp on valid rows
    valid_drift = valid["drift_pp"].dropna()
    mean_drift = valid_drift.mean() if len(valid_drift) > 0 else np.nan

    # clv_cents on valid rows
    valid_cents = valid["clv_cents"].dropna()
    mean_cents = valid_cents.mean() if len(valid_cents) > 0 else np.nan

    # ATS on ALL rows (ATS doesn't need same-point)
    has_result = subset["ats_outcome"].isin(["hit", "miss", "push"])
    graded = subset[has_result]
    hits = (graded["ats_outcome"] == "hit").sum()
    misses = (graded["ats_outcome"] == "miss").sum()
    pushes = (graded["ats_outcome"] == "push").sum()
    n_ats = hits + misses
    hit_rate, wilson_lo, wilson_hi = wilson_ci(hits, n_ats)

    return {
        "cell": cell, "sport": sport,
        "n_total": n_total, "n_excluded": n_excluded, "n_clv": n_clv,
        "mean_clv_pp": mean_clv, "se_clv": se_clv, "t_clv": t_clv,
        "mean_drift_pp": mean_drift, "mean_clv_cents": mean_cents,
        "null_mean": null_mean, "null_sd": null_sd,
        "hits": hits, "misses": misses, "pushes": pushes,
        "n_ats": n_ats, "hit_rate": hit_rate,
        "wilson_lo": wilson_lo, "wilson_hi": wilson_hi,
    }


def verdict(stats, min_n_clv=100):
    if stats is None:
        return "NO DATA"
    if stats["n_clv"] < 20:
        return f"INSUFFICIENT METHOD (valid N={stats['n_clv']})"
    if stats["n_clv"] < min_n_clv:
        return f"INSUFFICIENT N ({stats['n_clv']}/{min_n_clv})"
    if stats["t_clv"] >= 2.5 and stats["mean_clv_pp"] > 0:
        return "PASS"
    return "FAIL"


# ---- main ----

def main():
    print("LM-1b: Grading cells (paid-price CLV, comparability gate, registered C5)")
    print(f"Started: {datetime.now(timezone.utc).isoformat()}")
    t0 = time.time()

    tape = load_tape()
    events = load_events()
    print(f"Loaded tape ({len(tape):,} rows) and events ({len(events)} rows)")

    all_bets = []
    for sport in ["nfl", "ncaaf"]:
        print(f"\nGrading {sport.upper()}...")
        for fn, name in [(grade_c1, "C1"), (grade_c2, "C2"), (grade_c3, "C3"),
                         (grade_c4, "C4"),
                         (lambda t, e, s: grade_c5(t, e, s, registered_only=True), "C5"),
                         (grade_c6, "C6"),
                         (lambda t, e, s: grade_c5(t, e, s, registered_only=False), "C5-bidir")]:
            bets = fn(tape, events, sport)
            n_next = len([b for b in bets if b.get("timing") == "next"])
            print(f"  {name}: {len(bets)} instances ({n_next} next-snap)")
            all_bets.extend(bets)

    bets_df = pd.DataFrame(all_bets)
    bets_path = TAPE_DIR / "lm_cell_bets_2026.parquet"
    bets_df.to_parquet(bets_path, index=False)
    print(f"\nWrote {len(bets_df)} bet instances to {bets_path}")

    # Stats
    print("\n" + "=" * 80)
    print("CELL RESULTS (paid-price CLV, same-point only)")
    print("=" * 80)

    cells = ["C1", "C2", "C3", "C4", "C5", "C6", "C5-bidir"]
    results = []
    for cell in cells:
        for sport in ["nfl", "ncaaf"]:
            for timing in ["trigger", "next"]:
                s = grade_cell_stats(bets_df, cell, sport, timing)
                if s:
                    s["timing"] = timing
                    s["verdict"] = verdict(s)
                    results.append(s)

    results_df = pd.DataFrame(results)

    for timing in ["next"]:
        print(f"\n--- Timing: {timing} snapshot ---")
        for sport in ["nfl", "ncaaf"]:
            print(f"\n  {sport.upper()}:")
            sr = results_df[(results_df["sport"] == sport) & (results_df["timing"] == timing)]
            for _, r in sr.iterrows():
                excl = f" (excl {r['n_excluded']})" if r["n_excluded"] > 0 else ""
                ats_str = f"{int(r['hits'])}-{int(r['misses'])}" if r["n_ats"] > 0 else "—"
                print(f"    {r['cell']}: N_total={r['n_total']}, valid={r['n_clv']}{excl}, "
                      f"clv_pp={r['mean_clv_pp']:+.2f} (t={r['t_clv']:.2f}), "
                      f"drift_pp={r['mean_drift_pp']:+.2f}, "
                      f"cents={r['mean_clv_cents']:+.1f}, "
                      f"null={r['null_mean']:+.3f}±{r['null_sd']:.3f}, "
                      f"ATS={ats_str}, "
                      f"VERDICT: {r['verdict']}")

    elapsed = time.time() - t0
    print(f"\nElapsed: {elapsed:.1f}s")

    write_report(results_df, bets_df, elapsed)


def write_report(results_df, bets_df, elapsed):
    """Append LM-1b results to LM_INTERIM_2026-10-11.md (the retraction + new table
    are written by item 2; this writes the machine-readable closing table)."""
    # We write a SEPARATE file that item 2 will incorporate
    lines = []
    lines.append("# LM-1b Corrected Interim Grade — 2026-10-11")
    lines.append("")
    lines.append(f"Generated by `grade_lm_cells.py` (LM-1b) in {elapsed:.1f}s.")
    lines.append(f"Registry sha256: `edc972c6373b9c1d5c643320aa53c3b32e7eefcb7825d83b03543c169080e7a1`")
    lines.append("")
    lines.append("## Scale")
    lines.append("- `clv_pp` = Pinnacle de-vigged close (fair) − HR RAW implied (paid price), in pp")
    lines.append("- `drift_pp` = Pinnacle de-vigged close − HR de-vigged (fair-vs-fair movement)")
    lines.append("- `clv_cents` = (fair_close × decimal_payout − 1) × 100, in cents per dollar")
    lines.append("- `clv_valid` = True when close point == bet point (spreads/totals) or h2h")
    lines.append("- All means/t/null computed on clv_valid rows ONLY")
    lines.append("")

    # Pre-registrations
    lines.append("## Pre-registrations (written before re-running)")
    lines.append("")
    lines.append("- **P-LM1b-1**: C5-registered CLV mean ≤ 0 in both sports (paid-price scale)")
    lines.append("- **P-LM1b-2**: drift_pp for C5-bidirectional stays positive (~+1 pp) in both sports")
    lines.append("- **P-LM1b-3**: C2 paid-price CLV is negative in both sports")
    lines.append("")

    # Closing table
    cells = ["C1", "C2", "C3", "C4", "C5", "C6", "C5-bidir"]
    lines.append("## Closing Table")
    lines.append("")
    lines.append("| Cell | Sport | N_total | Valid | Excl | clv_pp | t | drift_pp | cents | ATS | Verdict |")
    lines.append("|------|-------|---------|-------|------|--------|---|----------|-------|-----|---------|")
    for cell in cells:
        for sport in ["nfl", "ncaaf"]:
            r = results_df[(results_df["cell"] == cell) & (results_df["sport"] == sport) &
                           (results_df["timing"] == "next")]
            if len(r) > 0:
                rr = r.iloc[0]
                ats_str = f"{int(rr['hits'])}-{int(rr['misses'])}" if rr["n_ats"] > 0 else "—"
                lines.append(
                    f"| {cell} | {sport.upper()} | {rr['n_total']} | {rr['n_clv']} | "
                    f"{rr['n_excluded']} | {rr['mean_clv_pp']:+.2f} | {rr['t_clv']:.2f} | "
                    f"{rr['mean_drift_pp']:+.2f} | {rr['mean_clv_cents']:+.1f} | "
                    f"{ats_str} | {rr['verdict']} |")
            else:
                lines.append(f"| {cell} | {sport.upper()} | 0 | 0 | 0 | — | — | — | — | — | NO DATA |")
    lines.append("")

    # Grade pre-registrations
    lines.append("## Pre-registration results")
    lines.append("")
    # P-LM1b-1
    c5_nfl = results_df[(results_df["cell"] == "C5") & (results_df["sport"] == "nfl") &
                         (results_df["timing"] == "next")]
    c5_ncaaf = results_df[(results_df["cell"] == "C5") & (results_df["sport"] == "ncaaf") &
                           (results_df["timing"] == "next")]
    c5_nfl_clv = c5_nfl.iloc[0]["mean_clv_pp"] if len(c5_nfl) > 0 else np.nan
    c5_ncaaf_clv = c5_ncaaf.iloc[0]["mean_clv_pp"] if len(c5_ncaaf) > 0 else np.nan
    p1_held = (not pd.isna(c5_nfl_clv) and c5_nfl_clv <= 0) and \
              (not pd.isna(c5_ncaaf_clv) and c5_ncaaf_clv <= 0)
    lines.append(f"- **P-LM1b-1**: C5 CLV NFL={c5_nfl_clv:+.2f}, NCAAF={c5_ncaaf_clv:+.2f}. "
                 f"{'HELD' if p1_held else 'DID NOT HOLD'}.")

    # P-LM1b-2
    cb_nfl = results_df[(results_df["cell"] == "C5-bidir") & (results_df["sport"] == "nfl") &
                         (results_df["timing"] == "next")]
    cb_ncaaf = results_df[(results_df["cell"] == "C5-bidir") & (results_df["sport"] == "ncaaf") &
                           (results_df["timing"] == "next")]
    cb_nfl_drift = cb_nfl.iloc[0]["mean_drift_pp"] if len(cb_nfl) > 0 else np.nan
    cb_ncaaf_drift = cb_ncaaf.iloc[0]["mean_drift_pp"] if len(cb_ncaaf) > 0 else np.nan
    p2_held = (not pd.isna(cb_nfl_drift) and cb_nfl_drift > 0) and \
              (not pd.isna(cb_ncaaf_drift) and cb_ncaaf_drift > 0)
    lines.append(f"- **P-LM1b-2**: C5-bidir drift NFL={cb_nfl_drift:+.2f}, NCAAF={cb_ncaaf_drift:+.2f}. "
                 f"{'HELD' if p2_held else 'DID NOT HOLD'}.")

    # P-LM1b-3
    c2_nfl = results_df[(results_df["cell"] == "C2") & (results_df["sport"] == "nfl") &
                         (results_df["timing"] == "next")]
    c2_ncaaf = results_df[(results_df["cell"] == "C2") & (results_df["sport"] == "ncaaf") &
                           (results_df["timing"] == "next")]
    c2_nfl_clv = c2_nfl.iloc[0]["mean_clv_pp"] if len(c2_nfl) > 0 else np.nan
    c2_ncaaf_clv = c2_ncaaf.iloc[0]["mean_clv_pp"] if len(c2_ncaaf) > 0 else np.nan
    p3_held = (not pd.isna(c2_nfl_clv) and c2_nfl_clv < 0) and \
              (not pd.isna(c2_ncaaf_clv) and c2_ncaaf_clv < 0)
    lines.append(f"- **P-LM1b-3**: C2 CLV NFL={c2_nfl_clv:+.2f}, NCAAF={c2_ncaaf_clv:+.2f}. "
                 f"{'HELD' if p3_held else 'DID NOT HOLD'}.")
    lines.append("")

    path = OUT_DIR / "LM_1b_CORRECTED_2026-10-11.md"
    path.write_text("\n".join(lines))
    print(f"Wrote report: {path}")


if __name__ == "__main__":
    main()
