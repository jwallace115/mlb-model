#!/usr/bin/env bash
# packet.sh <sport> <window-hours> <outdir>
# Build the input packet for Cowork's full-layer AI read.
# Zero API credits. Reads from the local repo only.
#
# Outputs:
#   sheet.csv    — the sheet (all lines the book of record quotes within the window)
#   template.csv — reader_v3 output on the sheet
#   news.csv     — ESPN archive items from the last 72h mentioning a team in the sheet
#   movement.csv — per-sheet-line: book open/now point+price+ts and consensus now
#   kalshi.csv   — newest Kalshi rows for the slate (if present)
#   sim.csv      — newest sim freeze rows (NFL only)
#   packet.md    — metadata: sport, window hours, row counts, file list
#
# P41: one command for the Cowork NCAAF/NFL read packet.
set -euo pipefail

SPORT="${1:?usage: packet.sh <sport> <window-hours> <outdir>}"
WINDOW_HOURS="${2:?usage: packet.sh <sport> <window-hours> <outdir>}"
OUTDIR="${3:?usage: packet.sh <sport> <window-hours> <outdir>}"

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
PY="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"

mkdir -p "$OUTDIR"

# 1. Sheet
"$PY" "$ROOT/nfl/pipeline/log_ai_opinions.py" sheet \
    --sport "$SPORT" --week 0 --window-hours "$WINDOW_HOURS" \
    --out "$OUTDIR/sheet.csv" 2>&1

# 2. Template (reader_v3)
"$PY" "$ROOT/nfl/pipeline/reader_v3.py" \
    "$OUTDIR/sheet.csv" "$OUTDIR/template.csv" \
    --sport "$SPORT" --root "$ROOT" 2>&1

# 3. News: ESPN archive items from last 72h mentioning a team in the sheet
"$PY" - "$SPORT" "$OUTDIR/sheet.csv" "$OUTDIR/news.csv" "$ROOT" <<'PYEOF'
import gzip, json, sys, csv
from datetime import datetime, timedelta, timezone
from pathlib import Path
import pandas as pd

sport, sheet_path, out_path, root = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4])
sheet = pd.read_csv(sheet_path)
teams = set()
for col in ("home_team", "away_team"):
    if col in sheet.columns:
        for t in sheet[col].dropna():
            # Last word of team name (mascot)
            teams.add(str(t).split()[-1].lower())

news_dir = root / "data" / "news_archive" / sport
now = datetime.now(timezone.utc)
cutoff = now - timedelta(hours=72)
rows = []
for sd in sorted(news_dir.glob("season=*")):
    for f in sorted(sd.glob("news_*Z.json.gz")):
        try:
            with gzip.open(f, "rt") as fh:
                data = json.load(fh)
        except Exception:
            continue
        if not isinstance(data, list):
            continue
        for art in data:
            headline = art.get("headline", "") or art.get("title", "")
            desc = art.get("description", "") or ""
            text = (headline + " " + desc).lower()
            pub = art.get("published", "")
            if pub:
                try:
                    pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                    if pub_dt < cutoff:
                        continue
                except Exception:
                    pass
            if any(t in text for t in teams):
                rows.append({"ts": pub[:19] if pub else "", "team": "",
                             "headline": headline[:300], "description": desc[:500],
                             "url": art.get("links", {}).get("web", {}).get("href", "") if isinstance(art.get("links"), dict) else ""})
with open(out_path, "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["ts", "team", "headline", "description", "url"])
    w.writeheader()
    for r in rows:
        w.writerow(r)
print(f"news: {len(rows)} items")
PYEOF

# 4. Movement: stub (pick_layers _line_movement requires the ledger; just copy sheet lines)
"$PY" - "$OUTDIR/sheet.csv" "$OUTDIR/movement.csv" "$ROOT" "$SPORT" <<'PYEOF'
import sys
from pathlib import Path
import pandas as pd

sheet_path, out_path, root, sport = sys.argv[1], sys.argv[2], Path(sys.argv[3]), sys.argv[4]
sheet = pd.read_csv(sheet_path)
# For each sheet line, just record the book's current point+price
rows = []
for _, r in sheet.iterrows():
    rows.append({"event_id": r["event_id"], "market_key": r["market_key"],
                 "player_name": r.get("player_name", ""), "line": r["line"],
                 "price_first": r["price_first"], "price_second": r.get("price_second"),
                 "source_utc": r["source_utc"]})
pd.DataFrame(rows).to_csv(out_path, index=False)
print(f"movement: {len(rows)} lines")
PYEOF

# 5. Kalshi
"$PY" - "$SPORT" "$OUTDIR/sheet.csv" "$OUTDIR/kalshi.csv" "$ROOT" <<'PYEOF'
import sys, re
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd

sport, sheet_path, out_path, root = sys.argv[1], sys.argv[2], sys.argv[3], Path(sys.argv[4])
kal_dir = root / "data" / "odds_archive" / "kalshi" / sport / "season=2026"
if not kal_dir.exists():
    pd.DataFrame().to_csv(out_path, index=False)
    print("kalshi: no directory")
    sys.exit(0)
snaps = sorted(kal_dir.glob("snap_*.parquet"))
if not snaps:
    pd.DataFrame().to_csv(out_path, index=False)
    print("kalshi: no snapshots")
    sys.exit(0)
df = pd.read_parquet(snaps[-1])
df.to_csv(out_path, index=False)
print(f"kalshi: {len(df)} rows from {snaps[-1].name}")
PYEOF

# 6. Sim (NFL only)
if [ "$SPORT" = "nfl" ]; then
    "$PY" - "$OUTDIR/sim.csv" "$ROOT" <<'PYEOF'
import sys
from pathlib import Path
import pandas as pd

out_path, root = sys.argv[1], Path(sys.argv[2])
sim_dir = root / "nfl" / "data" / "board"
best_file = None
for wd in sorted(sim_dir.glob("week=*/ai_opinions")):
    for p in sorted(wd.glob("ai_opinions_*.parquet")):
        try:
            rm = pd.read_parquet(p, columns=["reader_model"])
            if rm.reader_model.str.startswith("nfl_sim", na=False).any():
                best_file = p
        except Exception:
            pass
if best_file is None:
    pd.DataFrame().to_csv(out_path, index=False)
    print("sim: no sim freeze found")
else:
    df = pd.read_parquet(best_file)
    sim = df[df.reader_model.str.startswith("nfl_sim", na=False)]
    sim.to_csv(out_path, index=False)
    print(f"sim: {len(sim)} rows from {best_file.name}")
PYEOF
fi

# 7. Packet metadata
AS_OF=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
cat > "$OUTDIR/packet.md" <<MD
# Packet: $SPORT

- **as_of:** $AS_OF
- **sport:** $SPORT
- **window_hours:** $WINDOW_HOURS

## Files

| File | Lines |
|------|-------|
| sheet.csv | $(wc -l < "$OUTDIR/sheet.csv" | tr -d ' ') |
| template.csv | $(wc -l < "$OUTDIR/template.csv" | tr -d ' ') |
| news.csv | $(wc -l < "$OUTDIR/news.csv" | tr -d ' ') |
| movement.csv | $(wc -l < "$OUTDIR/movement.csv" | tr -d ' ') |
| kalshi.csv | $(wc -l < "$OUTDIR/kalshi.csv" | tr -d ' ') |
$([ -f "$OUTDIR/sim.csv" ] && echo "| sim.csv | $(wc -l < "$OUTDIR/sim.csv" | tr -d ' ') |" || echo "| sim.csv | (not applicable for $SPORT) |")
MD

echo ""
echo "=== packet.md ==="
cat "$OUTDIR/packet.md"
