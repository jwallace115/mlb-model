# WHY Summary — Week 2

Generated: 2026-10-22T11:20:26.177423+00:00


## Graded rows

- ai_nfl / moneyline / L: 3
- ai_nfl / prop:atd / L: 4
- ai_nfl / prop:atd / V: 2
- ai_nfl / prop:int / L: 1
- ai_nfl / prop:int / V: 2
- ai_nfl / prop:int / W: 1
- ai_nfl / prop:pass_att / L: 14
- ai_nfl / prop:pass_att / V: 2
- ai_nfl / prop:pass_att / W: 5
- ai_nfl / prop:pass_cmp / L: 11
- ai_nfl / prop:pass_cmp / W: 25
- ai_nfl / prop:pass_yds / L: 1
- ai_nfl / prop:pass_yds / V: 1
- ai_nfl / prop:rec / L: 128
- ai_nfl / prop:rec / V: 14
- ai_nfl / prop:rec / W: 91
- ai_nfl / prop:rec_yds / L: 1
- ai_nfl / prop:rec_yds / V: 2
- ai_nfl / prop:rush_att / L: 31
- ai_nfl / prop:rush_att / W: 27
- ai_nfl / prop:rush_yds / V: 1
- ai_nfl / prop:rush_yds / W: 2
- ai_nfl / spread / L: 10
- ai_nfl / spread / P: 1
- ai_nfl / spread / W: 4
- ai_nfl / total / L: 1
- ai_nfl / total / W: 4

## why_code_auto (losses)

- UNDEFINED: 181
- GARBAGE: 7
- UNRESOLVED: 5
- NOISE: 4
- NON_OFFENSIVE_TD: 2
- OT: 1

## why_code_auto (wins)

- UNDEFINED: 150
- OT: 3
- NOISE: 2
- TURNOVERS: 2
- GARBAGE: 1

## Thesis verdicts

- thesis_source=none: 344 rows
- thesis_source=nan: 0 rows
- thesis_source=tag_map: 20 rows

## Freeze-join accounting

- Freeze-sourced thesis: 0
- Tag-map thesis: 20
- No thesis: 344

## Unresolved player names (25 rows)

- Adam Trautman (8x): markets=['prop:rec']
- Noah Fant (5x): markets=['prop:rec']
- Drew Sample (4x): markets=['prop:rec']
- Jonnu Smith (2x): markets=['prop:rec']
- Stafford (2x): markets=['prop:pass_att', 'prop:pass_yds']
- Dart (1x): markets=['prop:pass_att']
- Singletary (1x): markets=['prop:rush_yds']
- OBJ (1x): markets=['prop:rec_yds']
- Odell Beckham Jr. (1x): markets=['prop:rec_yds']

## FLAGGED FOR THE TUESDAY READ


### 10 largest-|ln(A/L)| losses (10 rows)

- 2feb94d2bd51b327: prop:rush_att Jaxson Dart A=0.0 L=6.5 |ln|=6.477
- ce4e88920cd08fbe: prop:rec Jerry Jeudy A=0.0 L=2.5 |ln|=5.521
- a73068a713437767: prop:rec Jerry Jeudy A=0.0 L=2.5 |ln|=5.521
- fbec37bf0552420e: prop:rec Jerry Jeudy A=0.0 L=2.5 |ln|=5.521
- 4a05be0d91f64bc4: prop:rec Devin Singletary A=0.0 L=1.5 |ln|=5.011
- 9294f9be15aeeff5: prop:pass_att Jaxson Dart A=5.0 L=29.5 |ln|=1.775
- f6bd3710ae080832: prop:rec Quentin Johnston A=1.0 L=3.5 |ln|=1.253
- 4e91869dd066a66f: prop:rec Quentin Johnston A=1.0 L=3.5 |ln|=1.253
- f517ea50cc6f32d7: prop:rec Quentin Johnston A=1.0 L=3.5 |ln|=1.253
- 060ff32c4492ccd7: prop:rec Quentin Johnston A=1.0 L=3.5 |ln|=1.253

Total flagged: 10
