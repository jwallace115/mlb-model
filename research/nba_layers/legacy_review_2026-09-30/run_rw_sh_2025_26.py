"""Pre-registered test (PREREG_rw_sh_2025_26.md, sha256 90fc1d6e...). Cowork 2026-09-30."""
import pandas as pd, glob, numpy as np
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
N2A = {"Atlanta Hawks":"ATL","Boston Celtics":"BOS","Brooklyn Nets":"BKN","Charlotte Hornets":"CHA","Chicago Bulls":"CHI",
 "Cleveland Cavaliers":"CLE","Dallas Mavericks":"DAL","Denver Nuggets":"DEN","Detroit Pistons":"DET","Golden State Warriors":"GSW",
 "Houston Rockets":"HOU","Indiana Pacers":"IND","Los Angeles Clippers":"LAC","Los Angeles Lakers":"LAL","Memphis Grizzlies":"MEM",
 "Miami Heat":"MIA","Milwaukee Bucks":"MIL","Minnesota Timberwolves":"MIN","New Orleans Pelicans":"NOP","New York Knicks":"NYK",
 "Oklahoma City Thunder":"OKC","Orlando Magic":"ORL","Philadelphia 76ers":"PHI","Phoenix Suns":"PHX","Portland Trail Blazers":"POR",
 "Sacramento Kings":"SAC","San Antonio Spurs":"SAS","Toronto Raptors":"TOR","Utah Jazz":"UTA","Washington Wizards":"WAS"}
RW = {"ATL","CHI","DAL","DET","GSW","HOU","NYK","PHI","PHX","UTA"}; SH = {"ATL","BOS","DEN","IND","MIL","OKC","POR","SAS"}
cols = ["snapshot_utc","event_id","commence_time","home_team","away_team","bookmaker","market","outcome_name","point","price"]
fs = glob.glob(str(ROOT/"data/odds_archive/nba/history/lines_hourly/season=2025/close_*.parquet"))
c = pd.concat([pd.read_parquet(f, columns=cols) for f in fs]).drop_duplicates()
c = c[c.market=="totals"]
c["snap"]=pd.to_datetime(c.snapshot_utc,utc=True); c["ct"]=pd.to_datetime(c.commence_time,utc=True)
c = c[c.snap < c.ct]
last = c.loc[c.groupby(["event_id","bookmaker"]).snap.transform("max")==c.snap]
ov = last[last.outcome_name=="Over"][["event_id","bookmaker","point","price","ct","home_team","away_team"]]
wide = ov.pivot_table(index=["event_id"], columns="bookmaker", values=["point","price"], aggfunc="first")
wide.columns=[f"{a}_{b}" for a,b in wide.columns]
meta = ov.groupby("event_id").agg(ct=("ct","max"),home=("home_team","first"),away=("away_team","first"))
g = meta.join(wide).reset_index()
g["home"]=g.home.map(N2A); g["away"]=g.away.map(N2A)
g["date_et"]=(g.ct - pd.Timedelta(hours=5)).dt.strftime("%Y-%m-%d")
g = g[(g.date_et>="2025-10-21")&(g.date_et<="2026-04-12")]
p = pd.read_parquet(ROOT/"nba/data/predictions_4b.parquet")[["date","home_team","away_team","actual_total"]]
r = pd.read_parquet(ROOT/"nba/data/nba_results_log.parquet")[["game_date","home_team","away_team","actual_total"]].rename(columns={"game_date":"date"})
o = pd.concat([p,r]); o["date"]=pd.to_datetime(o.date).dt.strftime("%Y-%m-%d")
o = o.dropna(subset=["actual_total"]).drop_duplicates(["date","home_team","away_team"])
m = g.merge(o, left_on=["date_et","home","away"], right_on=["date","home_team","away_team"], how="left")
print("events in window", len(g), "| with outcome", m.actual_total.notna().sum(), "| with pinnacle", m.point_pinnacle.notna().sum())
m["sig"] = m.away.isin(RW) & m.home.isin(SH)
def dec(a): return np.where(a>0, 1+a/100, 1+100/np.abs(a))
def evaluate(d, book):
    d = d.dropna(subset=[f"point_{book}",f"price_{book}","actual_total"])
    push = d.actual_total==d[f"point_{book}"]; d=d[~push]
    win = d.actual_total>d[f"point_{book}"]
    pnl = np.where(win, dec(d[f"price_{book}"])-1, -1.0)
    n=len(d); roi=pnl.mean() if n else np.nan; se=pnl.std(ddof=1)/np.sqrt(n) if n>1 else np.nan
    return dict(n=n, pushes=int(push.sum()), hit=round(win.mean()*100,1) if n else np.nan, roi=round(roi*100,1), se=round(se*100,1), lo90=round((roi-1.2816*se)*100,1))
for book in ["pinnacle","hardrockbet","draftkings"]:
    print(book, "SIGNAL", evaluate(m[m.sig],book), "| NULL non-signal", evaluate(m[~m.sig],book))
s = m[m.sig].dropna(subset=["point_pinnacle","actual_total"]).copy()
s = s[s.actual_total!=s.point_pinnacle]; s["win"]=s.actual_total>s.point_pinnacle
s["pnl"]=np.where(s.win, dec(s.price_pinnacle)-1, -1.0); s["month"]=s.date_et.str[:7]
s["band"]=pd.cut(s.point_pinnacle,[0,225,235,400],labels=["<225","225-235",">235"])
for k in ["month","away","home","band"]:
    t=s.groupby(k,observed=True).agg(n=("win","size"),hit=("win","mean"),roi=("pnl","mean")); t.hit=(t.hit*100).round(1); t.roi=(t.roi*100).round(1)
    print(t.to_string()); print()
missing = m[m.sig & (m.actual_total.isna() | m.point_pinnacle.isna())]
print("signal games excluded (no outcome or no pinnacle):", len(missing))
