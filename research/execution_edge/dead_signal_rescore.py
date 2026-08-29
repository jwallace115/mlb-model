#!/usr/bin/env python3
"""
Re-score shelved signals against the Kalshi maker hurdle instead of the -110 vig.

WHAT THIS IS: a TRIAGE recalculation. It answers "which dead signals died against
a bar that no longer applies, and therefore deserve a second look?" It does NOT
resurrect anything. Nothing here is a finding.

TWO HARD FILTERS ARE APPLIED BEFORE ANY ARITHMETIC:

  FILTER 1 - CAUSE OF DEATH. A lower execution cost fixes an ECONOMICS kill. It
  fixes nothing about contamination, identity failure, or a noise-floor result.
  Signals that died of broken research stay dead and are listed as INELIGIBLE.

  FILTER 2 - VENUE. Kalshi must actually list the market, and the hurdle must
  have been MEASURED on that market. The 0.69% figure was measured on MLB game
  moneyline/totals only. Applying it to a 7c-wide team-total market would be the
  same class of error this project keeps making.

THE ARITHMETIC. For a two-way market whose vig-free fair price is 50c:
    ROI at -110          = 1.909*p - 1
    Kalshi maker EV/ctr  = (p - 0.50)*100 - hurdle_cents
    Kalshi maker ROI     = EV / 50c
The gain comes entirely from the break-even win rate moving from 52.38% to ~50.35%.

CRITICAL UNMEASURED RISK: adverse selection was measured on GENERAL MLB order
flow. If a signal correlates with what informed takers know, its own adverse
selection is worse than -0.347c and these numbers are too generous. That single
unknown can flip every row below. It is not a footnote.
"""
from datetime import datetime
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
OUT = ROOT / "research" / "execution_edge" / "dead_signal_rescore_2026-08-28.md"

HURDLE_C = 0.347          # measured, MLB game moneyline/totals, 60s horizon
BE_110 = 1 / 1.909        # 52.38%
BE_KALSHI = 0.50 + HURDLE_C / 100

# name, sport, market, kalshi_series, p(win rate), N, stated ROI, provenance note
ELIGIBLE = [
    ("ST02 Road-Trip Fatigue", "MLB", "FG totals UNDER", "KXMLBTOTAL", .5221, 2172,
     "-0.3%", "Clean economics kill. 'Market prices travel fatigue correctly.'"),
    ("adj_k_rate_last3", "MLB", "FG totals UNDER", "KXMLBTOTAL", .5214, 1539,
     "-0.64%", "ADJ family carries an IDENTITY defect - live dropped the p_under>0.57 co-filter."),
    ("ADJ_RUN_SUPP", "MLB", "FG totals UNDER", "KXMLBTOTAL", .5151, 3159,
     "-1.82%", "Same ADJ identity defect."),
    ("ADJ_CONTACT", "MLB", "FG totals UNDER", "KXMLBTOTAL", .5123, 3875,
     "-2.37%", "Same ADJ identity defect."),
    ("ADJ_HH", "MLB", "FG totals UNDER", "KXMLBTOTAL", .5109, 3081,
     "-2.58%", "Same ADJ identity defect."),
    ("ADJ_BB_RATE", "MLB", "FG totals UNDER", "KXMLBTOTAL", .5056, 1587,
     "-3.62%", "Also 50.0% on 16 resolved 2026 shadow - closer to noise."),
]

# market exists on Kalshi but the hurdle there is NOT measured
TIER2 = [
    ("F5/FG Path Mismatch (F3)", "MLB F5 totals UNDER", "KXMLBF5TOTAL", 3.0, .537, "+2.5%",
     "Best near-miss in the repo. But 71% of F5 lines are exactly 4.5, so the feature is largely a function of the FG line."),
    ("NRFI best combined filter", "MLB run-first-inning", "KXMLBRFI", 1.0, .557, "-3.0% @ -135",
     "Died explicitly of vig, not of signal. Needs Kalshi's RFI price - a win rate is not an edge."),
    ("Signal B HOME", "MLB F5 run line", "KXMLBF5SPREAD", 5.0, .539, "-6.2% @ -135",
     "Clean PIT number after removing xFIP lookahead. Wide market."),
    ("KP04 breaking-ball mismatch", "MLB strikeout props", "KXMLBKS", 3.0, .553, "~breakeven",
     "Zero fires in 226 games live - dead code, not a live signal."),
    ("TB props (book-specific)", "MLB total-base props", "KXMLBTB", 3.0, None, "-10% all-books",
     "Only survived on one book (BetOnline +22.6%, N=108). Almost certainly a pricing artifact."),
    ("NBA archetype pair", "NBA FG totals OVER", "KXNBA*", None, .514, "-1.8%",
     "Off-season in the capture window - no spread measured."),
]

INELIGIBLE = [
    ("V1 Ridge Totals Engine", "CONTAMINATION", "14 of 25 features used end-of-season FanGraphs aggregates."),
    ("F5 Totals Engine D1/D2", "CONTAMINATION", "Entirely parasitic on contaminated V1."),
    ("Team Totals E1/E2/E3", "CONTAMINATION+IDENTITY", "5/5 red flags; 'most contaminated object in the system'."),
    ("Over Scanner Wave 1 (all 10)", "CONTAMINATION", "V1 selection gate + discovery-validation leakage + 10-way multiple testing."),
    ("Signal B @ threshold 1.0", "CONTAMINATION", "Static season-final xFIP applied retroactively. Clean = coin flip."),
    ("C8 Command vs Stuff", "CONTAMINATION", "Frozen discovery medians move OOS from +3.48% to -12.06%."),
    ("MLB Moneyline Phases 1-3", "ECONOMICS but no residual", "0/8, 0/9, 0/10 survived validation. Nothing to re-score."),
    ("NBA ELITE_DEF2_at_ELITE_DEF", "NOISE", "43.0% OOS, -18% ROI."),
    ("W02 / D02 / H01 / H02", "NOISE", "Sign reversals across stages."),
    ("WNBA archetypes", "TRIAGE-ONLY", "Proxy odds, never validated on real prices."),
    ("NCAAF portal badge + ridge", "NO VENUE", "Kalshi lists no NCAAF market at all."),
    ("Golf signals", "NO VENUE + NOISE", "No Kalshi golf market; signals reversed anyway."),
]

def roi110(p): return 1.909 * p - 1
def kalshi_roi(p, hurdle=HURDLE_C): return ((p - .50) * 100 - hurdle) / 50

def main():
    L = []; W = L.append
    W("# Dead-Signal Re-Score Against the Kalshi Maker Hurdle")
    W(f"**Run:** {datetime.utcnow():%Y-%m-%d %H:%M} UTC · **API calls:** 0\n")
    W("> **This is triage, not a finding.** It identifies which shelved signals died")
    W("> against a bar that no longer applies. It resurrects nothing. Every row still")
    W("> needs its provenance re-verified before anyone acts on it.\n")
    W(f"Break-even win rate at -110: **{BE_110*100:.2f}%**  ")
    W(f"Break-even win rate as a Kalshi maker: **{BE_KALSHI*100:.2f}%**  ")
    W(f"Difference: **{(BE_110-BE_KALSHI)*100:.2f} percentage points**\n")
    W("That gap is the entire subject of this document.\n")

    W("## Tier 1 — market listed AND hurdle measured there\n")
    W("MLB full-game totals. Hurdle = 0.347c/contract, measured on 186,205 fills.\n")
    W("| Signal | N | Win rate | ROI @ -110 | Kalshi maker ROI | Flips? |")
    W("|---|---|---|---|---|---|")
    for nm, sp, mk, ser, p, n, stated, note in ELIGIBLE:
        k = kalshi_roi(p)
        W(f"| {nm} | {n:,} | {p*100:.2f}% | {stated} | **{k*100:+.2f}%** | "
          f"{'**YES**' if k > 0 else 'no'} |")
    W("")
    W("Every Tier 1 row flips positive. Before that reads as good news, note that the")
    W("largest, ADJ_RUN_SUPP at +2.33%, is a **2.3% ROI on a coin-flip-ish 51.5% signal**")
    W("— it survives only because the cost of transacting collapsed, not because the")
    W("signal got better. These are thin edges that need everything else to go right.\n")
    W("**Provenance flags on Tier 1:**\n")
    for nm, sp, mk, ser, p, n, stated, note in ELIGIBLE:
        W(f"- *{nm}* — {note}")
    W("")
    W("Five of the six are ADJ-family and share one identity defect: the deployed")
    W("object dropped a co-filter the research required. Re-scoring the research")
    W("object does not make the live object valid. Any revival is a rebuild.\n")

    W("## Tier 2 — market listed, hurdle NOT measured there\n")
    W("Median spreads measured on 1.63M quotes from the same capture. A wider spread")
    W("means more capture for a maker but also thinner books and probably more")
    W("toxicity — direction unknown, so no ROI is computed.\n")
    W("| Signal | Market | Kalshi series | Median spread | Win rate | Old result |")
    W("|---|---|---|---|---|---|")
    for nm, mk, ser, spc, p, stated, note in TIER2:
        W(f"| {nm} | {mk} | `{ser}` | {f'{spc:.1f}c' if spc else 'n/a'} | "
          f"{f'{p*100:.1f}%' if p else '—'} | {stated} |")
    W("")
    for nm, mk, ser, spc, p, stated, note in TIER2:
        W(f"- *{nm}* — {note}")
    W("")
    W("**NRFI is the conceptually cleanest case in the whole repo.** It was killed in")
    W("plain language for the right reason: *'the NRFI market has structural vig of")
    W("-135 that absorbs the available edge.'* That is a pure venue kill. But a 55.7%")
    W("win rate is not a 5.7-point edge — the edge is win rate minus Kalshi's price,")
    W("and Kalshi's RFI price is exactly what has never been measured.\n")

    W("## INELIGIBLE — a cheaper venue does not fix these\n")
    W("| Object | Cause of death | Why the hurdle is irrelevant |")
    W("|---|---|---|")
    for nm, cause, why in INELIGIBLE:
        W(f"| {nm} | {cause} | {why} |")
    W("")

    W("## The risk that can flip all of Tier 1\n")
    W("Adverse selection was measured on **general** MLB order flow: what a random")
    W("resting order experiences. A signal-driven order is not random. If your signal")
    W("keys on something informed takers also see — a lineup scratch, a weather move,")
    W("a late pitcher change — your fills arrive disproportionately when you are wrong,")
    W("and your true hurdle is worse than 0.347c.\n")
    W("Tier 1 edges run 0.21c to 1.86c per contract. **A signal-conditional hurdle of")
    W("1c would erase most of the table.** Measuring adverse selection conditional on")
    W("signal firing is the next real test, and it must come before any capital.\n")

    W("## Also unresolved\n")
    W("- Kalshi prices are assumed equal to vig-free sportsbook fair value. Never measured — that is the blocked cross-venue test.")
    W("- Fill rates are not modelled. A passive order that never fills earns nothing.")
    W("- NFL spreads here (6-7c) are from **mid-August, before the season**. Not representative; re-measure in-season.")
    W("- `PHASE7_CLEAN_KILLS.md` calls P09 permanently dead while `mlb_system_registry_v2.md` carries it as VALIDATED_SHADOW with live stake multipliers. Unrelated to this re-score, but it is a live contradiction with money attached.")

    OUT.write_text("\n".join(L))
    print(f"wrote {OUT}\n"); print("\n".join(L))

if __name__ == "__main__":
    main()
