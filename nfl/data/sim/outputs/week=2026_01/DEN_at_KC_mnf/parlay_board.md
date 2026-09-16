# DEN @ KC — 2026 Week 1 MNF (Mon 14 Sep, 8:15 ET) — manual Cowork run

Lines (Hard Rock, snapshot 2026-09-14T16:30Z): KC -2.5 (-110), total 43.5, KC ML -130. Props from the Sun 13 Sep 11:28Z pull.
Anchored sim (N=3,000, converged 4 iter): KC by 2.7, total 43.3, KC win 58.1%. Raw unanchored: DEN by 9.2, total 51.8.
Player layer: BUILT BY HAND — 2026 depth charts missing → automated week-1 shares were uniform (bug for Phase 4A). Used each
player's last 2025 shares (any team) + position floors for rookies, renormalised over the active list.

VERDICT: NO sim-backed SGP. Both teams have zero 2026 snaps; gaps vs Hard Rock (Kelce +30pp, Bryant +22pp, Sutton −19pp) are
stale-role signals, not edge. Same-game correlation lift among receptions legs ≈ 1.00 (no SGP bonus). Logged as UNBET picks.

| leg | book | implied | sim_raw | sim_cal | edge_pp | trust |
|---|---|---|---|---|---|---|
| Kelce rec O4.5 (TE) | +125 | 0.419 | 0.811 | 0.714 | +29.5 | stale-input flag |
| Pat Bryant rec O2.5 | +100 | 0.469 | 0.779 | 0.691 | +22.2 | stale-input flag |
| Rashee Rice rec O5.5 | -110 | 0.490 | 0.745 | 0.647 | +15.8 | stale-input flag |
| Thornton rec O1.5 | +110 | 0.449 | 0.573 | 0.500 | +5.1 | ok |
| Worthy rec O3.5 | +120 | 0.428 | 0.487 | 0.429 | +0.2 | ok |
| Walker III rec O3.5 (RB) | +125 | 0.414 | 0.447 | 0.428 | +1.5 | ok |
| Waddle rec O4.5 | -120 | 0.510 | 0.558 | 0.465 | -4.5 | ok |
| Sutton rec O3.5 | -170 | 0.592 | 0.401 | 0.398 | -19.3 | book far more confident → off |
| RJ Harvey rec O2.5 (RB) | -115 | 0.500 | 0.359 | 0.370 | -13.0 | off |
Team: KC ML cal 0.581; KC team total O22.5 0.516; DEN O20.5 0.441; game total O43.5 0.482. Spread straddles 3 → flagged.
Optional $5 flyer (Jeff's call): Kelce O4.5 +125 as a test of the 2025-role prior. Grade all legs after the game.

## COWORK TICKET (news + sim script layer), issued 2026-09-14 ~14:30 ET, lines as of Sun 13 Sep pull
Thesis: DEN pass rush + rookie LT + Mahomes first game back → KC runs Walker and throws short (Rice, Kelce); DEN attacks a
depleted KC secondary through Sutton. Sim script: KC by ~3, total ~43, close game. Weather non-factor.
CONFIDENCE (played): Walker 15+ rush att (14.5, −185) · Rice 5+ rec (4.5, −230) · Kelce 4+ rec (3.5, −180) ·
  Sutton 4+ rec (3.5, −170) · Mahomes 22+ comp (21.5, +100)
SWING (optional): Walker 17+ (+100) · Rice 6+ (−110) · Kelce 5+ (+125) · Sutton 5+ (+125) · Mahomes 22+ (+100)
Sim disagreement noted: Sutton (sim 40%, stale DEN split) — overruled by reporting. Kill condition: early Mahomes struggles.

### RE-PRICED on Hard Rock close pull (2026-09-14T18:10Z; KC -2.5 -108, total 43.5, KC ML -130)
Moves since Sun: Walker 16.5 +100→-110 (toward over); Mahomes att 32.5→33.5, comp 21.5 +100→-105 (toward passing);
Sutton 3.5 -170→-135 (cooled, Waddle); Dobbins att 12.5→11.5; RICE 5.5 -110→+120 (against; no news — full participant, starting).
CONFIDENCE (final): Walker 15+ (14.5, -195) · Rice 5+ (4.5, -175) · Kelce 4+ (3.5, -175) · Sutton 4+ (3.5, -135) · Mahomes 22+ comp (21.5, -105)
  independent product ≈ 8% (~+1150 fair); expected SGP price +650..+900; split KC-SGP + DEN two-leg if < +600.
SWING (final): Walker 17+ (+120) · Rice 6+ (+120) · Kelce 5+ (+125) · Sutton 5+ (+155) · Mahomes 22+ (-105); fair ≈ +5000.

### GRADED 2026-09-16 (KC 31, DEN 10) — 30 logged legs: 9 hit / 21 miss (grade_week.py, nflverse pbp)
Cash 5-leg +397 ($15): 4/5 — Worthy 3+ ✓, Bryant 2+ ✓, Walker TD ✓, Walker 50+ ✓, Waddle 4+ ✗. LOST.
Bonus 6-leg +2612 ($20 bonus): 1/6 — Walker 15+ ✓; Rice 6+, Kelce 5+, Sutton 4+, Mahomes 22+, Waddle 5+ ✗. LOST.
Confidence 5-leg (not played): 1/5 — Walker 15+ ✓; Rice 5+, Kelce 4+, Sutton 4+, Mahomes 22+ ✗.
Swing 5-leg (not played): 1/5. Sim unbet 9 legs: 2/9 (Bryant 3+, Harvey 3+).
Script read: KC blew it open and ran (Walker 17+ att) — Mahomes never needed 22 completions; Rice/Kelce volume
never came; DEN's passing game did not sustain (Sutton, Waddle under). The stale-input flag on Kelce 5+ / Rice 6+
(2025-role prior, zero 2026 snaps) was the right flag. Kill condition as written ("early Mahomes struggles") was the
wrong failure mode; the ticket died to a blowout the other way.
