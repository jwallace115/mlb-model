# Edge search for a Hard Rock (Florida) bettor — price, not prediction (Cowork, 2026-09-29)

Framing (Jeff: "Moneyball changed baseball — find it"): Moneyball bought what the market underpriced (OBP); it did
not out-predict everyone. The betting analog is buying what Hard Rock underprices. Tested from committed data:

1. **Stale Hard Rock game lines vs Pinnacle (NFL tape, 10 books every 30 min, 2026-09-06..09-29, 57 games).**
   HR quote vs Pinnacle no-vig at the SAME snapshot and point. Only 2.5% of HR quotes are >= 0 EV, 0.9% >= +2%.
   First detection per bet at >= +2%: 15 bets in 3 weeks, all moneylines; mean EV at detection +3.1%, and valued at
   Pinnacle's CLOSE +4.7% (share with positive CLV 0.47 — close moves both ways; EV by close holds). Small volume,
   real. NCAAF and MLB tapes have NO Hard Rock rows (API does not return HR for them) — untestable there.
   Script: ev_scan.py.
2. **Hard Rock NFL props vs Pinnacle / consensus (10-book pulls from 2026-09-27).** 1.2% of HR prop sides >= 0 EV vs
   Pinnacle, 0.1% >= +2% (2 sides). HR props sit on the consensus line with ~3.5% vig a side. No soft-prop edge at
   our pull cadence. Script: props_ev.py.
3. **Same-game correlation (K4 rows 2023-24: consensus closing lines + outcomes; teams from nflverse).** Real
   P(both) / market product: QB pass yds O + same-team WR rec yds O **1.25** (n=2,486, se 0.04); + TE 1.28; QB
   completions O + WR receptions O 1.22; the UNDER stack 1.23; RB rush att O + own QB pass att U 1.10; both QBs over
   1.10; opposite-team QB/WR 0.98, QB att / opp RB att 0.96. Jeff's slips (bets/ledger/pricing.parquet, private):
   Hard Rock cuts uncorrelated SGPs ~0.90-0.95 per extra leg and cuts stacked QB/WR slips much harder (0.74 per leg
   on a 9-leg Stafford/Adams stack) — it prices correlation. Whether its cut on a 2-leg QB/WR stack is smaller than
   the true 1.25 lift is UNMEASURED: needs Hard Rock's in-app price for a few 2-leg stacks. Script: corr.py.
4. **Boosts.** A 25% profit boost on a near-fair single at -110 is worth about +6-7% EV; on a 5-leg SGP carrying
   ~20-35% hold it is usually negative. Boosts pay most on the LOWEST-hold eligible bet.

Discipline: 1-2 are forward-style (prices as captured, scored against the sharp close) — no fitted parameters, the
2% threshold chosen before looking. 3 is measured on 2023-24 closes (market independence as the null); the lift is a
fact about outcomes, not a fitted model. No result here has been bet or tested forward yet.
Caveat: books limit accounts that consistently take stale prices or only bet boosts.
