#!/usr/bin/env python3
"""
SGP Phase 0 — Generate daily edge report.
"""
import json
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger("sgp_report")

BASE_DIR = Path(__file__).resolve().parent
FAIR_DIR = BASE_DIR / "fair_prices"
REPORT_DIR = BASE_DIR / "reports"
REPORT_DIR.mkdir(parents=True, exist_ok=True)


def generate(game_date=None):
    if game_date is None:
        files = sorted(FAIR_DIR.glob("fair_sgp_*.parquet"))
        if not files:
            logger.error("No fair price files found")
            return
        game_date = files[-1].stem.replace("fair_sgp_", "").replace("_", "-")

    fair_path = FAIR_DIR / f"fair_sgp_{game_date.replace('-','_')}.parquet"
    if not fair_path.exists():
        logger.error(f"No fair prices for {game_date}")
        return

    df = pd.read_parquet(fair_path)

    lines = []
    lines.append(f"## SGP Phase 0 Edge Report — {game_date}")
    lines.append(f"## Method: STRUCTURAL_CONTAINMENT (fair price = TB leg standalone)")
    lines.append("")

    for pair, pair_label in [("A", "Hits OVER 0.5 + TB OVER 1.5"),
                              ("B", "Hits OVER 0.5 + TB OVER 2.5")]:
        sub = df[df["pair_type"] == pair].sort_values("fair_combined_prob", ascending=False)
        lines.append(f"### Pair {pair}: {pair_label}")
        lines.append("")
        lines.append("| Player | Team | Book | Hits Price | TB Price | TB Impl% | Fair SGP | Book SGP | Excess Hold | EV |")
        lines.append("|--------|------|------|-----------|---------|---------|----------|---------|------------|------|")

        for _, r in sub.iterrows():
            player = r["player_name"]
            team = r.get("player_team", "") or "—"
            book = r["reference_book"]
            hits_p = f"{int(r['leg1_price']):+d}" if pd.notna(r["leg1_price"]) else "—"
            tb_p = f"{int(r['leg2_price']):+d}" if pd.notna(r["leg2_price"]) else "—"
            tb_impl = f"{r['leg2_implied_prob']*100:.1f}%" if pd.notna(r["leg2_implied_prob"]) else "—"
            fair = f"{int(r['fair_american_odds']):+d}" if pd.notna(r["fair_american_odds"]) else "—"

            if pd.notna(r.get("book_sgp_price")):
                bsgp = f"{int(r['book_sgp_price']):+d}"
                eh = f"{r['excess_hold']*100:+.1f}pp" if pd.notna(r.get("excess_hold")) else "—"
                ev = f"{r['ev_per_unit']:+.3f}" if pd.notna(r.get("ev_per_unit")) else "—"
            else:
                bsgp = "— log manually"
                eh = "—"
                ev = "—"

            lines.append(f"| {player} | {team} | {book} | {hits_p} | {tb_p} | {tb_impl} | {fair} | {bsgp} | {eh} | {ev} |")

        lines.append("")

    # Manual log summary
    n_a = len(df[df["pair_type"] == "A"])
    n_b = len(df[df["pair_type"] == "B"])
    logged = df[df["book_sgp_price"].notna()]
    n_logged = len(logged)
    same_book = logged[logged.get("same_book_comparison", False) == True] if "same_book_comparison" in logged.columns else pd.DataFrame()
    cross = n_logged - len(same_book)

    lines.append("### Manual Log Summary")
    lines.append(f"- Pair A candidates: {n_a} | Pair B candidates: {n_b}")
    lines.append(f"- Manually logged today: {n_logged}")
    if n_logged > 0:
        avg_eh = logged["excess_hold"].mean() * 100
        avg_ev = logged["ev_per_unit"].mean()
        lines.append(f"- Average excess hold on logged: {avg_eh:+.1f}pp")
        lines.append(f"- Average EV: {avg_ev:+.3f} units")
        lines.append(f"- Same-book comparisons: {len(same_book)} | Cross-book: {cross}")
    else:
        lines.append("- No SGP prices logged yet — use log_sgp_price.py to enter book prices")

    # Cumulative tracker summary
    tracker_path = BASE_DIR / "summary_tracker.parquet"
    if tracker_path.exists():
        try:
            tracker = pd.read_parquet(tracker_path)
            cum_n = len(tracker)
            cum_eh = tracker["excess_hold"].mean() * 100 if tracker["excess_hold"].notna().any() else 0
            cum_sb = int(tracker["same_book_comparison"].sum()) if "same_book_comparison" in tracker.columns else 0
            lines.append("")
            lines.append(f"Cumulative logged: {cum_n} | Avg excess hold: {cum_eh:+.1f}% | Same-book comparisons: {cum_sb}")
        except Exception:
            pass

    report = "\n".join(lines)
    out_path = REPORT_DIR / f"edge_report_{game_date.replace('-','_')}.md"
    out_path.write_text(report)
    logger.info(f"Saved: {out_path}")

    print(report)
    return report


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None)
    args = parser.parse_args()
    generate(args.date)
