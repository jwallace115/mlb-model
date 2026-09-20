#!/usr/bin/env python3
"""
Ingest Hard Rock Bet "All_Bets_Export" files into a private bet ledger.

  drop exports in   bets/inbox/          (any filename; .xls as downloaded)
  run               python3 shared/pipeline/ingest_hardrock_bets.py
  raw files go to   bets/archive/        hr_export_<last-placed>_<sha8>.xls   (moved, never deleted)
  ledger            bets/ledger/slips.parquet, legs.parquet, pricing.parquet
  your labels       bets/tags.csv        slip_id,source,notes   (source: ours | group | other | ?)

bets/ is GITIGNORED: the repo is public and this is a personal wagering record. Only this
script is committed.

The export is SpreadsheetML with an .xls name and bare ampersands ("Texas A&M"). 13-cell rows
are slips; 14-cell rows with a blank first cell are the legs of the slip above. Leg prices are
the decimal prices AT BET TIME (verified: every cross-game slip's price equals the product of
its leg prices to 3-4 decimals).

Exports overlap night to night and statuses change (Open -> Won/Lost), so slips are UPSERTED by
Bet Slip ID: the newest export wins, first_seen is kept. Times are the app's local time
(America/New_York), stored as naive local timestamps.

HALTS (non-zero exit, nothing written, file left in inbox) on: a changed header, an
unrecognised row shape, a leg before any slip, duplicate slip ids inside one export.
"""
import hashlib, re, shutil, sys, xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
BETS = ROOT / "bets"
INBOX, ARCHIVE, LEDGER, TAGS = BETS / "inbox", BETS / "archive", BETS / "ledger", BETS / "tags.csv"
NS = "urn:schemas-microsoft-com:office:spreadsheet"
HDR = ['Date Placed', 'Status', 'League', 'Match', 'Bet Type', 'Market', 'Price', 'Wager',
       'Winnings', 'Payout', 'Potential Payout', 'Result', 'Bet Slip ID']


class Halt(Exception):
    pass


def _dt(s):
    return pd.to_datetime(s, format="%d %b %Y @ %I:%M%p", errors="coerce") if s else pd.NaT


def _num(s):
    try:
        return float(s)
    except (TypeError, ValueError):
        return float("nan")


def parse_export(path):
    raw = Path(path).read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"&(?!(?:amp|lt|gt|quot|apos|#\d+|#x[0-9A-Fa-f]+);)", "&amp;", raw)
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as e:
        raise Halt(f"not parseable as SpreadsheetML: {e}")
    rows = [[(c.find(f"{{{NS}}}Data").text if c.find(f"{{{NS}}}Data") is not None else None)
             for c in r.findall(f"{{{NS}}}Cell")] for r in root.iter(f"{{{NS}}}Row")]
    if not rows or rows[0] != HDR:
        raise Halt(f"header changed: {rows[0] if rows else None}")
    slips, legs, cur = [], [], None
    for i, r in enumerate(rows[1:], start=2):
        r = [(x or "").strip() for x in r]
        if len(r) == 13 and r[0]:
            cur = r[12]
            slips.append(dict(slip_id=cur, placed_local=_dt(r[0]), status=r[1], league=r[2],
                              match=r[3], bet_type=r[4], market=r[5], price_dec=_num(r[6]),
                              wager=_num(r[7]), winnings=_num(r[8]), payout=_num(r[9]),
                              potential_payout=_num(r[10]), result_time_local=_dt(r[11])))
        elif len(r) == 14 and not r[0]:
            if cur is None:
                raise Halt(f"leg before any slip at row {i}")
            legs.append(dict(slip_id=cur, leg_status=r[1], league=r[2], match=r[3], market=r[4],
                             selection=r[5], price_dec=_num(r[6]), start_local=_dt(r[11])))
        else:
            raise Halt(f"unrecognised row {i}: {len(r)} cells, first cell {r[0]!r}")
    S = pd.DataFrame(slips)
    L = pd.DataFrame(legs, columns=["slip_id", "leg_status", "league", "match", "market",
                                    "selection", "price_dec", "start_local"])
    if S.empty:
        raise Halt("no slips in export")
    if S.slip_id.duplicated().any():
        raise Halt("duplicate slip ids inside one export")
    if S.placed_local.isna().any():
        raise Halt("unparseable 'Date Placed' value")
    L["leg_no"] = L.groupby("slip_id").cumcount() + 1
    return S, L


def pricing(S, L):
    """Quoted parlay price vs the product of its single-leg prices. A Void or Push leg is
    priced at 1.0 — Hard Rock reprices the slip without it (verified on two slips)."""
    if L.empty:
        return pd.DataFrame()
    live = L.assign(p=L.price_dec.where(~L.leg_status.isin(["Void", "Push"]), 1.0),
                    counted=~L.leg_status.isin(["Void", "Push"]))
    g = live.groupby("slip_id")
    P = pd.DataFrame({"legs": g.size(), "legs_priced": g.counted.sum(), "product": g.p.prod(),
                      "games": live[live.counted].groupby("slip_id").match.nunique(),
                      "legs_won": g.leg_status.apply(lambda s: int((s == "Win").sum())),
                      "legs_lost": g.leg_status.apply(lambda s: int((s == "Lose").sum()))})
    P["games"] = P["games"].fillna(0).astype(int)
    P["same_game_extra"] = (P.legs_priced - P.games).clip(lower=0)
    P = P.join(S.set_index("slip_id")[["placed_local", "league", "status", "price_dec", "wager"]])
    P["ratio"] = P.price_dec / P["product"]
    P["ratio_per_extra_leg"] = P.ratio.where(P.same_game_extra > 0) ** (1 / P.same_game_extra.where(P.same_game_extra > 0))
    return P.reset_index()


def _upsert(old, new, key, seen_at):
    new = new.copy()
    new["last_seen_utc"] = seen_at
    if old is None or old.empty:
        new["first_seen_utc"] = seen_at
        return new
    first = old.drop_duplicates(key).set_index(key)["first_seen_utc"]
    keep = old[~old[key].isin(new[key].unique())]
    new["first_seen_utc"] = new[key].map(first).fillna(seen_at)
    return pd.concat([keep, new], ignore_index=True)


def ingest(inbox=INBOX, archive=ARCHIVE, ledger=LEDGER, tags=TAGS):
    for d in (inbox, archive, ledger):
        d.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in inbox.iterdir() if p.is_file() and not p.name.startswith("."))
    if not files:
        print("inbox empty"); return 0
    sp, lp = ledger / "slips.parquet", ledger / "legs.parquet"
    S_old = pd.read_parquet(sp) if sp.exists() else None
    L_old = pd.read_parquet(lp) if lp.exists() else None
    parsed = []
    for f in files:                       # parse everything first: a bad file halts before any write
        S, L = parse_export(f)
        parsed.append((f, S, L))
    parsed.sort(key=lambda t: t[1].placed_local.max())     # oldest export first, newest wins
    for f, S, L in parsed:
        seen = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        n_new = int((~S.slip_id.isin(S_old.slip_id)).sum()) if S_old is not None else len(S)
        n_chg = 0
        if S_old is not None:
            m = S.merge(S_old[["slip_id", "status"]], on="slip_id", suffixes=("", "_old"))
            n_chg = int((m.status != m.status_old).sum())
        S_old, L_old = _upsert(S_old, S, "slip_id", seen), _upsert(L_old, L, "slip_id", seen)
        sha = hashlib.sha256(f.read_bytes()).hexdigest()[:8]
        dest = archive / f"hr_export_{S.placed_local.max():%Y%m%dT%H%M}_{sha}{f.suffix or '.xls'}"
        if dest.exists():
            dest = archive / f"{dest.stem}_{datetime.now(timezone.utc):%H%M%S}{dest.suffix}"
        print(f"{f.name}: {len(S)} slips / {len(L)} legs, {S.placed_local.min():%Y-%m-%d} -> "
              f"{S.placed_local.max():%Y-%m-%d} | new {n_new}, status changed {n_chg} -> {dest.name}")
        S_old.sort_values("placed_local").to_parquet(sp, index=False)
        L_old.sort_values(["slip_id", "leg_no"]).to_parquet(lp, index=False)
        shutil.move(str(f), str(dest))
    pricing(S_old, L_old).to_parquet(ledger / "pricing.parquet", index=False)
    known = pd.read_csv(tags, dtype=str) if tags.exists() else pd.DataFrame(columns=["slip_id", "source", "notes"])
    add = S_old[~S_old.slip_id.isin(known.slip_id)].sort_values("placed_local")
    if len(add):
        desc = add.placed_local.dt.strftime("%Y-%m-%d %H:%M") + " " + add.league + " $" + add.wager.round(2).astype(str) + " " + add.status
        known = pd.concat([known, pd.DataFrame({"slip_id": add.slip_id, "source": "?", "notes": desc})], ignore_index=True)
        known.to_csv(tags, index=False)
    print(f"ledger: {len(S_old)} slips, {len(L_old)} legs | untagged: {(known.source == '?').sum()} (edit {tags.relative_to(ROOT)})")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(ingest())
    except Halt as e:
        print(f"HALT: {e}"); sys.exit(1)
