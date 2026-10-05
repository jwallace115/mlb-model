# NHL pilot — Cowork "layers" parlay, slate 2026-10-01 (logged pre-kick 2026-10-01 ~23:20Z; append-only)
Reader: Cowork (Claude, edge-hunt chat). Stake: Jeff, $20-25, for fun. Book: Hard Rock (in-app). Rule N54: a pick is the
reader's opinion; layers are inputs; graded on hit rate AND on the Pinnacle close per leg; never "validated"/"+EV".
Five legs, five SEPARATE games (Jeff's rule), only games tipping 00:00Z or later (the 23:00Z games were unreachable).
Prices: DraftKings via ESPN scoreboard ~23:00Z (no Odds API from the bridge; no Pinnacle tonight). Props: NO prop
prices were obtainable — each prop leg carries a price-to-beat; skip the leg if Hard Rock is worse.

## Layer 1 — HISTORICAL (2025-26 NHL play-by-play, 1,312 games, nhl/cache/pbp; computed tonight, scripts in
## logs/cowork_stage/layers_2026-10-01/hist.py + hist2.py)
| team | gf/g | ga/g | sf/g | sa/g | win% | home win% | over 5.5% | over 6.5% |
|---|---|---|---|---|---|---|---|---|
| MIN | 3.32 | 2.93 | 29.5 | 29.8 | .561 | .561 | .61 | .51 |
| NSH | 3.01 | 3.28 | 28.1 | 29.9 | .463 | .512 | .54 | .43 |
| SEA | 2.76 | 3.21 | 25.9 | 29.8 | .415 | .463 | .55 | .35 |
| CGY | 2.59 | 3.16 | 28.4 | 30.2 | .415 | .561 | .52 | .35 |
| CHI | 2.60 | 3.35 | 25.0 | 30.3 | .354 | .341 | .51 | .40 |
| UTA | 3.27 | 2.93 | 27.7 | 26.2 | .524 | .537 | .54 | .46 |
| FLA | 3.06 | 3.37 | 28.3 | 27.0 | .488 | .561 | .61 | .51 |
| SJS | 3.06 | 3.56 | 25.9 | 29.8 | .476 | .512 | .60 | .51 |
| EDM | 3.44 | 3.28 | 29.9 | 26.9 | .500 | .537 | .68 | .59 |
| VAN | 2.63 | 3.85 | 26.3 | 30.1 | .305 | .220 | .66 | .56 |
Players (per game, 2025-26): McDavid 3.78 SOG, P(3+)=.71, P(4+)=.48, 1.68 pts, P(2+ pts)=.52 | Celebrini 3.55 SOG,
P(3+)=.67, P(4+)=.48, P(1+ pt)=.73 | Kaprizov 3.54 SOG, P(3+)=.67, P(4+)=.41, P(1+ pt)=.72 | Boldy 3.46, P(3+)=.64 |
Guenther 3.06, P(3+)=.65 | Forsberg 3.05, P(3+)=.59 | Keller 2.74 | Draisaitl 2.91 SOG, 1.49 pts, P(2+ pts)=.42.
Goalies (2025-26): Saros sv% .892, 26.1 sv/g | Wallstedt .909 (35 gp) | Wolf .898, 24.7 sv/g | Daccord .894 | Knight .898 |
Vejmelka .896 | Askarov .882, 3.38 GA/g | Lankinen .876, 3.43 GA/g | Levi: no NHL sample in the file.
H2H 2025-26: MIN-NSH 4 games, 3 to OT (3-2, 3-2, 6-5 OT, 2-1); SEA-CGY split 1-2 (SEA 5-1 at CGY); CHI won 3 of 4 vs UTA
(4-0 at UTA) — with Bedard.

## Layer 2 — NEWS (DailyFaceoff starting goalies ~23:00Z; NHL.com projected lineups 2026-10-01; RotoWire/FanDuel)
- MIN@NSH 00:00Z: Saros CONFIRMED; Wallstedt unconfirmed (Gustavsson OUT lower body; Faber OUT skull fracture).
  MIN lines: Kaprizov–Yurov–Shabanov; Coleman–Eriksson Ek–Boldy; Hughes–Spurgeon. DK: MIN −142 / NSH +120, total 5.5.
- SEA@CGY 01:00Z: Wolf CONFIRMED; Daccord unconfirmed. Huberdeau OUT (hip) for CGY; Samoskevich OUT for SEA.
  DK: CGY −112 / SEA −108, total 5.5.
- CHI@UTA 01:30Z: BEDARD OUT (shoulder); Mangiapane OUT; Knight / Vejmelka both unconfirmed; UTA: Lamoureux OUT.
  CHI top line Bertuzzi–Frondell–Kane. DK: UTA −112 / CHI −108; UTA −1.5 +225; total 6.5 (O +114 / U −135).
- FLA@SJS 02:00Z: Schmid (FLA) / Askarov (SJS) unconfirmed; Marchand OUT (lower body), Gadjovich OUT; SJS Gaudette OUT.
  FLA lines: B. Tkachuk–Barkov–Reinhart; Verhaeghe–Bennett–M. Tkachuk. FD: SJS +126 (FLA ≈ −150); total 6.5.
- EDM@VAN 02:00Z: Levi (EDM) / Lankinen (VAN; Demko OUT hip). EDM OUT: Hyman (2 weeks), Nugent-Hopkins, Janmark,
  Dickinson, Savoie, Andersen — second line Jones–Dach–Kapanen. VAN: Chytil OUT. FD: EDM −205 / VAN +168; EDM −1.5 +114;
  total 6.5 (O −122 / U +100). Records: EDM 0-0-1, VAN 1-0 (both already played once).

## Layer 3 — REASONING (why each leg, what would make it wrong)
1. CHI @ UTA — **UTA ML (DK −112; price-to-beat −115).** Biggest layer disagreement on the slate: last season UTA +0.34
   goal differential/game vs CHI −0.75, UTA 52% wins vs CHI 35%, and tonight CHI is without Bedard (its only 3+ SOG,
   1+ pt/g forward) — yet the market has it a coin flip at home for UTA. Wrong if: Vejmelka is not the starter or
   CHI's new top-six (Frondell/Kane) is better than last year's, which the history cannot see; H2H last year was 3-1 CHI.
2. MIN @ NSH — **Kaprizov OVER 2.5 SOG (price-to-beat −150; if the line is 3.5, take OVER at −105 or better).**
   67% of games last season; new wingers (Yurov, Shabanov) make him the line's only established shooter; Hughes–Spurgeon
   feed; NSH allowed 29.9 sf/g. Wrong if: a 3-to-OT grinder like last year's H2H (3-2, 3-2, 2-1) with MIN protecting.
3. FLA @ SJS — **Celebrini OVER 2.5 SOG (price-to-beat −140).** 67% last season at 3.55/g, SJS's whole offence runs
   through him; FLA without Marchand and with an unconfirmed Schmid. Wrong if: FLA's 27.0 sa/g (best on the slate)
   suppresses SJS volume as it did last year (SJS 25.9 sf/g).
4. EDM @ VAN — **McDavid 2+ POINTS (price-to-beat +100).** 52% last season; tonight EDM's second line is Jones–Dach–
   Kapanen with Hyman/RNH/Janmark/Dickinson/Savoie out, so the offence concentrates on McDavid–Draisaitl–Podkolzin and
   the PP1; VAN allowed 3.85 GA/g (worst in the league) and starts Lankinen (.876) with Demko out. Wrong if: VAN's 1-0
   start is real or EDM's thin lineup drags the whole game under.
5. SEA @ CGY — **CGY ML (DK −112; price-to-beat −115).** Weakest leg, stated as such: Wolf confirmed at home vs an
   unconfirmed Daccord; CGY 56% at home last season; two bottom-five offences (2.59 / 2.76 gf/g) make this a goalie
   game and Wolf (.898, 2.82 GA/g) is the better of the two. Huberdeau out cuts CGY's playmaking. Wrong if: SEA's
   5-1 at Calgary last January was the real matchup read.
Alternates if a leg is unavailable or priced worse than the price-to-beat: EDM@VAN OVER 6.5 (−122; both teams' games went
over 6.5 at 56-59% last season, both goalies below .880 or unproven); FLA@SJS Over 6.5 (51% hist — fair, not a lean).

## PARLAY (5 legs, five games, implied at the prices-to-beat ≈ +2050)
UTA ML (−112) · Kaprizov O2.5 SOG (−150) · Celebrini O2.5 SOG (−140) · McDavid 2+ pts (+100) · CGY ML (−112)
Honesty line: every leg is a reader lean at roughly market price; none is a ledger edge; the historical layer is one
prior season of box-score rates (the same inputs the books price), the news layer is public, the reasoning layer is
the only thing the market might not share — and that is the thing being measured, not assumed. Expected value at these
prices ≈ the parlay vig (negative) unless the reasoning layer carries information.
Grade 2026-10-02: hit per leg + the Pinnacle close per leg (from the tape / E-WO2-style pull if credits allow).
