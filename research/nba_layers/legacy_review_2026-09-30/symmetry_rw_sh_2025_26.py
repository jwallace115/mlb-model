"""
RW@SH symmetry check (A5, NS1) — compute UNDER ROI on the same signal games
at Pinnacle's last pre-tip under price.

PRE-REGISTRATION (written before computing):
  - Prediction: over ROI + under ROI on the 101 signal games lies in [-6.0%, -2.0%]
    (the vig drag: both sides pay ~4.5% vig, so sum should be near -vig = -4 to -5%)
  - NULL CONTROL: the same sum on non-signal games lies in the same [-6.0%, -2.0%] band.
  - If either is outside, STOP and report. Do not change any reported RW@SH number.

Imports loaders from run_rw_sh_2025_26.py — does NOT edit that file.
"""
import pandas as pd
import numpy as np
import glob
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
# Odds archive is gitignored; use main checkout for local-only data
MAIN_ROOT = Path.home() / "mlb-model"

# ── Re-use the exact data pipeline from run_rw_sh_2025_26.py ──
# (we import the constants and rebuild the same dataframe)
N2A = {
    "Atlanta Hawks": "ATL", "Boston Celtics": "BOS", "Brooklyn Nets": "BKN",
    "Charlotte Hornets": "CHA", "Chicago Bulls": "CHI", "Cleveland Cavaliers": "CLE",
    "Dallas Mavericks": "DAL", "Denver Nuggets": "DEN", "Detroit Pistons": "DET",
    "Golden State Warriors": "GSW", "Houston Rockets": "HOU", "Indiana Pacers": "IND",
    "Los Angeles Clippers": "LAC", "Los Angeles Lakers": "LAL", "Memphis Grizzlies": "MEM",
    "Miami Heat": "MIA", "Milwaukee Bucks": "MIL", "Minnesota Timberwolves": "MIN",
    "New Orleans Pelicans": "NOP", "New York Knicks": "NYK", "Oklahoma City Thunder": "OKC",
    "Orlando Magic": "ORL", "Philadelphia 76ers": "PHI", "Phoenix Suns": "PHX",
    "Portland Trail Blazers": "POR", "Sacramento Kings": "SAC", "San Antonio Spurs": "SAS",
    "Toronto Raptors": "TOR", "Utah Jazz": "UTA", "Washington Wizards": "WAS",
}
RW = {"ATL", "CHI", "DAL", "DET", "GSW", "HOU", "NYK", "PHI", "PHX", "UTA"}
SH = {"ATL", "BOS", "DEN", "IND", "MIL", "OKC", "POR", "SAS"}

cols = ["snapshot_utc", "event_id", "commence_time", "home_team", "away_team",
        "bookmaker", "market", "outcome_name", "point", "price"]
fs = glob.glob(str(MAIN_ROOT / "data/odds_archive/nba/history/lines_hourly/season=2025/close_*.parquet"))
c = pd.concat([pd.read_parquet(f, columns=cols) for f in fs]).drop_duplicates()
c = c[c.market == "totals"]
c["snap"] = pd.to_datetime(c.snapshot_utc, utc=True)
c["ct"] = pd.to_datetime(c.commence_time, utc=True)
c = c[c.snap < c.ct]
last = c.loc[c.groupby(["event_id", "bookmaker"]).snap.transform("max") == c.snap]

# Over side
ov = last[last.outcome_name == "Over"][["event_id", "bookmaker", "point", "price", "ct", "home_team", "away_team"]]
# Under side
un = last[last.outcome_name == "Under"][["event_id", "bookmaker", "point", "price"]]
un = un.rename(columns={"point": "under_point", "price": "under_price"})

wide_ov = ov.pivot_table(index="event_id", columns="bookmaker", values=["point", "price"], aggfunc="first")
wide_ov.columns = [f"{a}_{b}" for a, b in wide_ov.columns]

wide_un = un.pivot_table(index="event_id", columns="bookmaker", values=["under_point", "under_price"], aggfunc="first")
wide_un.columns = [f"{a}_{b}" for a, b in wide_un.columns]

meta = ov.groupby("event_id").agg(ct=("ct", "max"), home=("home_team", "first"), away=("away_team", "first"))
g = meta.join(wide_ov).join(wide_un).reset_index()
g["home"] = g.home.map(N2A)
g["away"] = g.away.map(N2A)
g["date_et"] = (g.ct - pd.Timedelta(hours=5)).dt.strftime("%Y-%m-%d")
g = g[(g.date_et >= "2025-10-21") & (g.date_et <= "2026-04-12")]

# Outcomes
p = pd.read_parquet(ROOT / "nba/data/predictions_4b.parquet")[["date", "home_team", "away_team", "actual_total"]]
r = pd.read_parquet(ROOT / "nba/data/nba_results_log.parquet")[
    ["game_date", "home_team", "away_team", "actual_total"]
].rename(columns={"game_date": "date"})
o = pd.concat([p, r])
o["date"] = pd.to_datetime(o.date).dt.strftime("%Y-%m-%d")
o = o.dropna(subset=["actual_total"]).drop_duplicates(["date", "home_team", "away_team"])
m = g.merge(o, left_on=["date_et", "home", "away"], right_on=["date", "home_team", "away_team"], how="left")
m["sig"] = m.away.isin(RW) & m.home.isin(SH)


def dec(a):
    return np.where(a > 0, 1 + a / 100, 1 + 100 / np.abs(a))


def evaluate_over(d, book):
    d = d.dropna(subset=[f"point_{book}", f"price_{book}", "actual_total"])
    push = d.actual_total == d[f"point_{book}"]
    d = d[~push]
    win = d.actual_total > d[f"point_{book}"]
    pnl = np.where(win, dec(d[f"price_{book}"]) - 1, -1.0)
    n = len(d)
    roi = pnl.mean() if n else np.nan
    se = pnl.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    return dict(n=n, pushes=int(push.sum()), hit=round(win.mean() * 100, 1) if n else np.nan,
                roi=round(roi * 100, 1), se=round(se * 100, 1))


def evaluate_under(d, book):
    d = d.dropna(subset=[f"under_point_{book}", f"under_price_{book}", "actual_total"])
    push = d.actual_total == d[f"under_point_{book}"]
    d = d[~push]
    win = d.actual_total < d[f"under_point_{book}"]
    pnl = np.where(win, dec(d[f"under_price_{book}"]) - 1, -1.0)
    n = len(d)
    roi = pnl.mean() if n else np.nan
    se = pnl.std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    return dict(n=n, pushes=int(push.sum()), hit=round(win.mean() * 100, 1) if n else np.nan,
                roi=round(roi * 100, 1), se=round(se * 100, 1))


print("=" * 80)
print("RW@SH SYMMETRY CHECK (A5)")
print("=" * 80)

print("\n--- PRE-REGISTRATION ---")
print("Prediction: over ROI + under ROI on signal games in [-6.0%, -2.0%]")
print("Null control: same sum on non-signal games in [-6.0%, -2.0%]")
print()

book = "pinnacle"
sig = m[m.sig]
non = m[~m.sig]

ov_sig = evaluate_over(sig, book)
un_sig = evaluate_under(sig, book)
ov_non = evaluate_over(non, book)
un_non = evaluate_under(non, book)

print(f"SIGNAL games (n_over={ov_sig['n']}, n_under={un_sig['n']}):")
print(f"  Over  ROI: {ov_sig['roi']:+.1f}% (hit {ov_sig['hit']}%, SE {ov_sig['se']}pp)")
print(f"  Under ROI: {un_sig['roi']:+.1f}% (hit {un_sig['hit']}%, SE {un_sig['se']}pp)")
sum_sig = ov_sig['roi'] + un_sig['roi']
print(f"  SUM (over + under): {sum_sig:+.1f}%")

print(f"\nNON-SIGNAL games (n_over={ov_non['n']}, n_under={un_non['n']}):")
print(f"  Over  ROI: {ov_non['roi']:+.1f}% (hit {ov_non['hit']}%, SE {ov_non['se']}pp)")
print(f"  Under ROI: {un_non['roi']:+.1f}% (hit {un_non['hit']}%, SE {un_non['se']}pp)")
sum_non = ov_non['roi'] + un_non['roi']
print(f"  SUM (over + under): {sum_non:+.1f}%")

print("\n--- VERDICTS ---")
sig_in_band = -6.0 <= sum_sig <= -2.0
non_in_band = -6.0 <= sum_non <= -2.0
print(f"Signal sum {sum_sig:+.1f}%: {'IN BAND [-6, -2]' if sig_in_band else 'OUTSIDE BAND — STOP'}")
print(f"Non-signal sum {sum_non:+.1f}%: {'IN BAND [-6, -2]' if non_in_band else 'OUTSIDE BAND — STOP'}")

if not sig_in_band or not non_in_band:
    print("\nSTOP: At least one check is outside the pre-registered band.")
    print("Do not change any reported RW@SH number. Jeff decides.")
