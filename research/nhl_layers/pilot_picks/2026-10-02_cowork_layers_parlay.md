# NHL pilot — Cowork "layers" parlay, slate 2026-10-02 (logged pre-kick 2026-10-02 ~21:05Z; append-only)
Reader: Cowork (Claude, edge-hunt chat). Stake: Jeff, $20-25, for fun. Book: Hard Rock (in-app). Rule N54: a pick is the
reader's opinion; layers are inputs; graded on hit rate AND on the Pinnacle close per leg; never "validated"/"+EV".
Five legs, five SEPARATE games. Prices = Pinnacle from `live_lines_2026-10-02_2037Z.md` (nhl/pipeline/pull_nhl_live_lines.py,
31 credits, 288,580 -> 288,549). Price-to-beat = Pinnacle; skip a leg if Hard Rock is more than 10 cents worse.

## Layer 1 — HISTORICAL (2025-26 play-by-play, 1,312 games; logs/cowork_stage/layers_2026-10-01/hist.py + hist2.py)
| team | gf/g | ga/g | sf/g | sa/g | win% | home win% | over 5.5% | over 6.5% |
|---|---|---|---|---|---|---|---|---|
| NYR | 2.90 | 3.05 | 25.3 | 28.9 | .415 | .341 | .48 | .39 |
| DET | 2.94 | 3.15 | 28.4 | 28.0 | .500 | .512 | .60 | .45 |
| WSH | 3.21 | 2.98 | 28.4 | 28.5 | .524 | .610 | .54 | .41 |
| CAR | 3.61 | 2.93 | 32.5 | 24.3 | .646 | .707 | .65 | .54 |
| BOS | 3.32 | 3.05 | 27.3 | 30.0 | .549 | .707 | .57 | .51 |
| WPG | 2.82 | 3.17 | 26.5 | 27.9 | .427 | .463 | .57 | .48 |
| STL | 2.82 | 3.15 | 25.5 | 27.9 | .451 | .488 | .48 | .40 |
| DAL | 3.40 | 2.76 | 25.6 | 26.5 | .610 | .634 | .54 | .49 |
| ANA | 3.33 | 3.51 | 31.1 | 28.6 | .524 | .585 | .66 | .60 |
| VGK | 3.23 | 3.05 | 29.3 | 24.7 | .476 | .488 | .57 | .46 |
H2H 2025-26: NYR 2-1 vs DET (4-1, 1-2, 4-1) · WSH 2-1 vs CAR · BOS 2-0 vs WPG (6-3, 6-1) · DAL 4-1 vs STL, all within
2 goals · ANA 3-0 vs VGK (4-3 OT, 4-3, 4-3).
Players (2025-26 per game): DeBrincat 3.54 SOG, P(4+)=.44, P(1+pt)=.65 | Pastrnak 3.40, P(4+)=.45, P(1+pt)=.74 |
K. Connor 3.39, P(4+)=.41 | Robertson 3.70, P(4+)=.48, P(2+pts)=.37 | Rantanen 2.23 SOG, 1.20 pts, P(1+pt)=.75 |
Gauthier 3.78, P(4+)=.50 | Eichel 3.61, P(3+)=.74, P(2+pts)=.36 | Ovechkin 2.99, P(3+)=.62 | Zibanejad 2.65, P(3+)=.47 |
Scheifele 1.26 pts/g, P(2+)=.43 | Stone 1.22 pts, P(1+)=.72.
Goalies: Shesterkin .911 | Garand (NYR backup): no NHL sample in file | Gibson .898, 23.1 sv/g | L. Thompson .907,
25.2 sv/g, P(sv>26.5)=.40 | Bussi .892, 21.2 sv/g | Swayman .907 | Hellebuyck .893 (SUSPENDED) | Skinner: no WPG
sample | Hofer .906 | Oettinger .896, 23.1 sv/g | Dostal .887 | Hart .882 (18 gp).

## Layer 2 — NEWS (DailyFaceoff ~20:45Z; NHL.com projected lineups 2026-10-02; results via CBS/ESPN)
This season so far: NYR 1-1-0 (lost opener, beat TBL 5-1 last night, Shesterkin 24 sv) · CAR 0-0-1 (OT loss) · BOS 1-0 ·
VGK 1-0 · DET, WSH, WPG, STL, DAL, ANA: openers tonight.
- NYR@DET 6:40 ET: NYR on a BACK-TO-BACK; DailyFaceoff lists Garand (unconfirmed) and Pinnacle hangs a Garand saves line
  (27.5) and no Shesterkin line -> market expects the backup. DET: LARKIN OUT (upper body), Bernard-Docker out; Gibson
  likely. DET line 1 DeBrincat–Copp–Raymond. NYR: Korpisalo injured. PIN: DET −128 / NYR +116; total 6.0 (−101/−111).
- WSH@CAR 7:10 ET: Thompson CONFIRMED (WSH); Bussi likely (CAR; Andersen not listed). CAR: SETH JARVIS OUT (shoulder).
  WSH: Sandin out; line 1 Tuch–Dubois–Wilson, line 2 Ovechkin–Strome–Leonard. PIN: CAR −141 / WSH +127; total 6.0.
- BOS@WPG 8:10 ET: HELLEBUYCK SUSPENDED -> Stuart Skinner (unconfirmed) for WPG; Salomonsson out. BOS: McAVOY
  SUSPENDED, Poitras out; Swayman (unconfirmed). PIN: WPG −115 / BOS +104; total 6.0.
- STL@DAL 9:10 ET: Hofer / Oettinger (both unconfirmed). DAL: DUCHENE OUT; line 1 Robertson–Hintz–Seguin, line 2
  Hryckowian–Johnston–Rantanen. STL: Mailloux, Tucker out; line 2 Buchnevich–McTavish–McMichael. PIN: DAL −181 / STL
  +162; DAL −1.5 +143; total 6.0.
- ANA@VGK 10:10 ET: Dostal / Carter Hart (both unconfirmed; Hill not listed). ANA: TROY TERRY OUT (hip), Helleson, Moore
  out; line 1 Greer–Carlsson–Gauthier. VGK: nobody out; Marner on line 2 with Karlsson/Howden. PIN: VGK −193 / ANA +172;
  total 6.5 (O −120 / U +106).

## Layer 3 — REASONING
1. BOS @ WPG — **Boston ML (PIN +104; take at +100 or better).** Biggest disagreement on the slate. Last season BOS was
   the better team (.549 vs .427, +0.27 vs −0.35 goal diff/game) and beat WPG 6-3 and 6-1; tonight WPG is without
   Hellebuyck (suspended) and starts Skinner, who has no track record for them. Market has WPG favoured on home ice
   alone. Wrong if: McAvoy's suspension matters more than Hellebuyck's, or last year's WPG was the fluke.
2. NYR @ DET — **Detroit ML (PIN −128; take at −130 or better).** Rangers on a back-to-back after a 5-1 win, with the
   backup Garand (Pinnacle's goalie lines say so); DET rested at home. Historical layer is neutral-to-NYR (NYR 2-1 H2H;
   NYR .415 vs DET .500). Larkin OUT is the real cost. Wrong if: Shesterkin starts (check DailyFaceoff at 6 ET) — then drop.
3. WSH @ CAR — **Logan Thompson OVER 25.5 saves (PIN −123; take at −125 or better).** Carolina shot 32.5/g last season
   and 34+ at home; Thompson is confirmed and carried 25.2 sv/g on a defence that allowed 28.5. 30 CAR shots × .907 ≈ 27
   saves. The leg wins whether Carolina wins or not, which is why it's here instead of CAR −141. Wrong if: WSH blows out
   CAR early (fewer shots) or Thompson is pulled.
4. STL @ DAL — **Jason Robertson OVER 3.5 SOG (PIN +108; take at +100 or better).** 3.70/g last season, 4+ in 48% of
   games (implied 48% at +108 — fair), on line 1 with Hintz/Seguin and PP1; Duchene out moves more of the offence to his
   line. Wrong if: a tight DAL–STL game as last year's (all within 2 goals).
5. ANA @ VGK — **Cutter Gauthier OVER 3.5 SOG (PIN +110; take at +100 or better).** 3.78/g, 4+ in 50% of games (implied
   47.6%), Terry OUT concentrates ANA's shooting on Gauthier–Carlsson; VGK allowed only 24.7 sa/g, the main risk.
   Alternate here: ANA@VGK OVER 6.5 (−120) — ANA games went over 6.5 60% last season, ANA 3-0 vs VGK all 4-3s.
Alternates if a leg is off: CAR ML (−141); Rantanen 1+ point (−221, 75% last season); Pastrnak 1+ point (−240, 74%).

## PARLAY (5 legs, five games; implied at Pinnacle ≈ +2800)
BOS ML (+104) · DET ML (−128) · L. Thompson O25.5 saves (−123) · Robertson O3.5 SOG (+108) · Gauthier O3.5 SOG (+110)
Honesty line: every leg is a reader lean at roughly market price; none is a ledger edge. Historical layer = one prior
season of public box-score rates; news layer = public; the reasoning layer is the only thing the market might not share,
and it is being measured, not assumed. Grade 2026-10-03 on hit per leg and Pinnacle close per leg.
