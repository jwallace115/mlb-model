#!/usr/bin/env python3
"""
Record report for AI picks (owners ai_*/sim_*): W/L/P/V, units at the logged price,
CLV, by reader / rank-within-freeze / conf bin / market family / day ET.

Reads the ledger view; maps source_file → reader_model via the manifests.
No member rows are read or printed.

Output: PICKS_LEDGER_DIR/record_report.txt and record_report.json (never committed;
the dryrun ledger version lands under ~/private_picks/).

VM cron 45 10 * * * after picks_clv.

OPS-R1 Item 4, P55.
"""
import collections
import glob as globmod
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import picks_ledger as pl

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")
ET = timezone(timedelta(hours=-4))


def _load_manifests(root):
    """source_file basename → (reader_model, window) from freeze manifests."""
    rm = {}
    for mf in globmod.glob(str(root / "*/data/board/*/ai_opinions/manifest.json")):
        for e in json.load(open(mf)):
            rm[e["file"]] = (e.get("reader_model") or "?", e.get("window") or "?")
    return rm


def _reader_label(r, manifests):
    sf = os.path.basename(str(r.get("source_file") or ""))
    m = manifests.get(sf, ("?", "?"))[0]
    if m.startswith("nfl_sim"):
        return "sim_v1"
    if m == "claude-fable-5-1":
        return "cowork"
    if m.startswith("claude"):
        return m[:16]
    if m.startswith("reader_v3"):
        return m  # keep reader_v3 or reader_v3b
    return m[:16] if m != "?" else (r.get("owner") or "?") + "(no manifest)"


def _units(r):
    res = r.get("result")
    p = r.get("price_american")
    if res not in ("W", "L") or p is None:
        return 0.0
    p = float(p)
    if res == "L":
        return -1.0
    return p / 100.0 if p > 0 else 100.0 / abs(p)


def _market_family(m):
    m = str(m)
    if m in ("h2h", "moneyline", "ml"):
        return "moneyline"
    if m in ("spread", "spreads"):
        return "spread"
    if m in ("total", "totals"):
        return "total"
    if "prop" in m or m.startswith("player_"):
        return "prop:" + m.replace("prop:", "").replace("player_", "")
    return m


def _conf_bin(c):
    try:
        c = float(c)
    except (TypeError, ValueError):
        return "n/a"
    if c == 0:
        return "0"
    if c < 5:
        return "1-4"
    if c < 10:
        return "5-9"
    if c < 15:
        return "10-14"
    if c < 20:
        return "15-19"
    if c < 30:
        return "20-29"
    return "30+"


def _rank_bucket(rank):
    if rank <= 5:
        return "top5"
    if rank <= 10:
        return "top10"
    if rank <= 20:
        return "top20"
    return "21+"


def compute_ranks(rows):
    """Assign rank-within-freeze (by conf desc) and tier bucket to each row."""
    by_freeze = collections.defaultdict(list)
    for r in rows:
        by_freeze[(r.get("source_file"), r.get("owner"))].append(r)
    for key, lst in by_freeze.items():
        lst.sort(key=lambda r: -(float(r.get("conf") or 0)))
        for i, r in enumerate(lst, 1):
            r["_rank"] = i
            r["_rank_bucket"] = _rank_bucket(i)


def annotate(rows, manifests):
    """Add computed fields to each row."""
    for r in rows:
        r["_reader"] = _reader_label(r, manifests)
        r["_units"] = _units(r)
        r["_fam"] = _market_family(r.get("market"))
        r["_bin"] = _conf_bin(r.get("conf"))
        try:
            logged = datetime.fromisoformat(str(r["logged_utc"]).replace("Z", "+00:00"))
            r["_day"] = logged.astimezone(ET).strftime("%a %m-%d")
        except Exception:
            r["_day"] = "?"


def _table_line(key, counter, units_sum, n_clv_vals):
    W, L, P, V, O = counter["W"], counter["L"], counter["P"], counter["V"], counter["open"]
    n = W + L
    wp = f"{100 * W / n:.0f}" if n else "-"
    roi = f"{100 * units_sum / n:+.1f}" if n else "-"
    return {"key": str(key), "W": W, "L": L, "P": P, "V": V, "open": O,
            "win_pct": wp, "units": round(units_sum, 2), "roi_pct": roi, "n_clv": n_clv_vals}


def build_table(rows, key_fn, clv_by_pid=None):
    """Group rows by key_fn, return list of summary dicts."""
    groups = collections.defaultdict(lambda: collections.Counter())
    units = collections.defaultdict(float)
    clv_counts = collections.defaultdict(int)
    for r in rows:
        k = key_fn(r)
        groups[k][r.get("result") or "open"] += 1
        units[k] += r["_units"]
        if clv_by_pid and r.get("pick_id") in clv_by_pid:
            clv_counts[k] += 1
    return [_table_line(k, groups[k], units[k], clv_counts[k]) for k in sorted(groups, key=str)]


def generate(root=None, ledger_dir=None):
    """Generate the full report. Returns (text, json_data)."""
    root = Path(root or ROOT)
    ledger_dir = Path(ledger_dir or LEDGER_DIR)

    if not ledger_dir.exists():
        return "HALT: ledger dir does not exist", {}

    rows = [r for r in pl.view(ledger_dir)
            if str(r.get("owner", "")).startswith(("ai_", "sim_"))]

    manifests = _load_manifests(root)

    # CLV
    clv_by_pid = {}
    clv_path = ledger_dir / "clv.jsonl"
    if clv_path.exists():
        for line in open(clv_path):
            try:
                d = json.loads(line)
                clv_by_pid[d["pick_id"]] = d
            except Exception:
                pass

    annotate(rows, manifests)
    compute_ranks(rows)

    lines = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    lines.append(f"record report — generated {ts}; {len(rows)} rows (owners ai_*/sim_*)")

    tables = {}
    tables["by_owner_reader"] = build_table(rows, lambda r: (r.get("owner"), r["_reader"]), clv_by_pid)
    tables["by_reader_rank"] = build_table(rows, lambda r: (r["_reader"], r.get("_rank_bucket", "?")), clv_by_pid)
    tables["by_reader_bin"] = build_table(rows, lambda r: (r["_reader"], r["_bin"]), clv_by_pid)
    tables["by_reader_fam"] = build_table(rows, lambda r: (r["_reader"], r["_fam"]), clv_by_pid)
    tables["by_reader_day"] = build_table(rows, lambda r: (r["_reader"], r["_day"]), clv_by_pid)

    for name, tbl in tables.items():
        lines.append(f"\n== {name}")
        lines.append(f"{'key':50} {'W':>4} {'L':>4} {'P':>3} {'V':>3} {'open':>5} {'win%':>6} {'units':>8} {'ROI%':>6}")
        for t in tbl:
            lines.append(f"{t['key'][:50]:50} {t['W']:>4} {t['L']:>4} {t['P']:>3} {t['V']:>3} {t['open']:>5} {t['win_pct']:>6} {t['units']:>+8.2f} {t['roi_pct']:>6}")

    text = "\n".join(lines) + "\n"
    json_data = {"generated_utc": ts, "n_rows": len(rows), "tables": tables}
    return text, json_data


def main():
    if not LEDGER_DIR.exists():
        print(f"HALT: PICKS_LEDGER_DIR={LEDGER_DIR} does not exist")
        sys.exit(1)

    text, json_data = generate()
    print(text)

    out_txt = LEDGER_DIR / "record_report.txt"
    out_json = LEDGER_DIR / "record_report.json"
    out_txt.write_text(text)
    with open(out_json, "w") as f:
        json.dump(json_data, f, indent=2, default=str)
    print(f"wrote {out_txt} and {out_json}")


if __name__ == "__main__":
    main()
