# WHY Summary — Week 5

Generated: 2026-10-12T03:51:21.514772+00:00


## Graded rows

- ai_nfl / moneyline / L: 4
- ai_nfl / prop:atd / L: 8
- ai_nfl / prop:atd / V: 5
- ai_nfl / prop:int / L: 4
- ai_nfl / prop:int / W: 4
- ai_nfl / prop:pass_att / L: 4
- ai_nfl / prop:pass_att / W: 4
- ai_nfl / prop:pass_cmp / L: 6
- ai_nfl / prop:pass_cmp / W: 2
- ai_nfl / prop:pass_td / L: 6
- ai_nfl / prop:pass_td / W: 2
- ai_nfl / prop:pass_yds / L: 4
- ai_nfl / prop:pass_yds / W: 4
- ai_nfl / prop:rec / L: 21
- ai_nfl / prop:rec / V: 4
- ai_nfl / prop:rec / W: 22
- ai_nfl / prop:rec_yds / L: 25
- ai_nfl / prop:rec_yds / V: 4
- ai_nfl / prop:rec_yds / W: 15
- ai_nfl / prop:rush_att / L: 8
- ai_nfl / prop:rush_att / W: 5
- ai_nfl / prop:rush_yds / L: 9
- ai_nfl / prop:rush_yds / V: 4
- ai_nfl / prop:rush_yds / W: 11
- ai_nfl / spread / L: 1
- ai_nfl / spread / W: 3
- ai_nfl / total / L: 4
- sim_nfl / prop:rec / L: 3
- sim_nfl / prop:rec / V: 1
- sim_nfl / prop:rec / W: 6
- sim_nfl / prop:rush_att / L: 1
- sim_nfl / prop:rush_att / W: 1

## why_code_auto (losses)

- SCRIPT: 28
- EFFICIENCY: 27
- SHARE_OTHER: 26
- TURNOVERS: 5
- NOISE: 4

## why_code_auto (wins)

- SHARE_OTHER: 24
- SCRIPT: 22
- EFFICIENCY: 19
- UNDEFINED: 5
- TURNOVERS: 3

## Thesis verdicts

- thesis_source=tag_map: 169 rows
- thesis_source=nan: 0 rows
- thesis_source=none: 23 rows

## Freeze-join accounting

- Freeze-sourced thesis: 0
- Tag-map thesis: 169
- No thesis: 23

## Unresolved player names (13 rows)

- Ted Hurst III (9x): markets=['prop:rec_yds', 'prop:rec']
- Tyler Goodson (4x): markets=['prop:rush_yds']

## PBP vs official stat mismatches (4 rows)

- Dak Prescott: prop:pass_att official=42.0 pbp=43.0
- Dak Prescott: prop:pass_att official=42.0 pbp=43.0
- Dak Prescott: prop:pass_att official=42.0 pbp=43.0
- Dak Prescott: prop:pass_att official=42.0 pbp=43.0

## FLAGGED FOR THE TUESDAY READ


### Top 20 picks (92 rows)

- bd36b7aa96dbf6e0: moneyline None → L
- 75fe1ae661a80bc9: prop:atd Bauer Sharp → L
- 5e7eaa38eebf70d4: prop:atd Ko Kieft → V
- da5635691812b101: prop:atd Payne Durham → L
- 8e9722c769e0465c: prop:int Dak Prescott → L
- 07f631040009ace9: prop:pass_td Dak Prescott → W
- 9a246bac7cfec42d: prop:pass_td Jalon Daniels → L
- 41a4db37b0b4b03c: prop:rec_yds Bucky Irving → W
- a67d98276231e324: prop:rec_yds Cade Otton → W
- 6c144effcaf9f4ae: prop:rec_yds Jake Ferguson → W
- e7cf26be622a8b42: prop:rec_yds Javonte Williams → L
- 91311655580d4432: prop:rec_yds Ryan Flournoy → L
- 749e462af110faef: prop:rec Emeka Egbuka → L
- 478d1719920bff28: prop:rec George Pickens → L
- 20aa0517c628c9a3: prop:rec Jake Ferguson → W
- d8adff9737950db0: prop:rec Kenny Gainwell → L
- 778448da002356f6: prop:rec Ted Hurst III → V
- fec8edef23a93b52: prop:rush_yds Dak Prescott → W
- 41e37b2e0fbd2389: prop:rush_yds Kenny Gainwell → W
- a60a55979e79c8a0: spread None → W
- dbec1a208c72b57a: moneyline None → L
- b28298238b30d97a: prop:pass_att Jalon Daniels → W
- a7d68a375cbcfdbe: prop:pass_td Dak Prescott → W
- 91edee84032fa420: prop:pass_td Jalon Daniels → L
- 5b334fdf34782926: prop:rec_yds Bucky Irving → W
- 3554cc36b4574db3: prop:rec_yds Jake Ferguson → W
- 1e07b14bb9fac925: prop:rec Bucky Irving → W
- 80ec492285f9ddbf: prop:rec Cade Otton → W
- 77f10609af2a90da: prop:rec CeeDee Lamb → W
- c3becee15ca3e604: prop:rec Chris Godwin → W
- 1e305fc4dfa1d095: prop:rec Emeka Egbuka → L
- 834f3f13afe3ab6e: prop:rec George Pickens → L
- 3682a3194e7fa485: prop:rec Jake Ferguson → W
- 0d54c7201b1b4380: prop:rec Javonte Williams → W
- 8550a0e624665852: prop:rec Kenny Gainwell → L
- 6d2d59d7c96ae76a: prop:rec Ryan Flournoy → L
- bb2907d59cb4a09e: prop:rush_yds Dak Prescott → W
- 1491e6a9b25a2fba: prop:rush_yds Kenny Gainwell → L
- c5f7ddc7bcf1fe50: prop:rush_yds Tyler Goodson → V
- 28b89c2723eae071: total None → L
- 1fa21b4aacb3365a: prop:pass_att Dak Prescott → L
- 303ed210c4573ef4: prop:pass_att Jalon Daniels → L
- d1460539055f0b48: prop:pass_td Jalon Daniels → L
- 079d1f3d6ac1f4d2: prop:pass_yds Dak Prescott → W
- 74b5e706510a27ce: prop:rec_yds Bucky Irving → L
- 42717b625585906e: prop:rec_yds CeeDee Lamb → L
- 6fe0591ce28741e1: prop:rec_yds George Pickens → W
- ecc8d8fed1bb5c0e: prop:rec_yds Javonte Williams → L
- cea2ecb28515f312: prop:rec Bucky Irving → L
- 68276fb749d3520d: prop:rec Chris Godwin → L
- e9311221feec80c1: prop:rec George Pickens → L
- eb61335bd6087e60: prop:rec Javonte Williams → W
- 87409406994b2a9a: prop:rec Tez Johnson → W
- fb681da7dbdc58b2: prop:rush_att Bucky Irving → L
- 675cec94d7b43f47: prop:rush_att Javonte Williams → L
- f594c2f3863c00d4: prop:rush_yds Bucky Irving → L
- 4875907a072a484b: prop:rush_yds Dak Prescott → W
- 1a4131ca7e328661: prop:rush_yds Javonte Williams → L
- d92f33dade3f62b6: spread None → W
- 6c3c357cc35784f7: total None → L
- d76f6f5a43b26294: prop:pass_att Dak Prescott → L
- c4f74aa0a5d5dfa8: prop:pass_att Jalon Daniels → L
- a81611ebfac21586: prop:pass_yds Dak Prescott → W
- de62fde174d381b8: prop:rec_yds Bucky Irving → L
- efdda781e0bf3fea: prop:rec_yds CeeDee Lamb → L
- 95c956ca1b23b130: prop:rec_yds George Pickens → W
- 49036359a8aa694e: prop:rec_yds Javonte Williams → L
- 6e78ee347103139f: prop:rec Bucky Irving → L
- 40a4649cbc7b3ccf: prop:rec Cade Otton → L
- cf952c97e11b3e6e: prop:rec George Pickens → L
- 3f8f0afe7421990e: prop:rec Jake Ferguson → W
- 6471f7c0c66722dc: prop:rec Javonte Williams → W
- fa2661e31517036c: prop:rec Ryan Flournoy → W
- 35bbd2c1c70bff71: prop:rec Ted Hurst III → V
- 39c3ae6d458bc5a9: prop:rec Tez Johnson → W
- a8e54e9eec26c0d2: prop:rush_att Javonte Williams → L
- 08f1007fd90e4b72: prop:rush_yds Bucky Irving → L
- bae93ea7c3afad22: prop:rush_yds Dak Prescott → W
- 85c1c63eab837965: prop:rush_yds Javonte Williams → L
- fa899e6e09af82a3: spread None → W
- 376fee49aad451a2: prop:rec Bucky Irving → L
- 4c3a93570b067036: prop:rec Cade Otton → L
- c54182764810bbfc: prop:rec CeeDee Lamb → W
- 6290f7962daeeff6: prop:rec Emeka Egbuka → W
- 9d1a6c6770d71f11: prop:rec George Pickens → L
- f2efc854ca27318d: prop:rec Jake Ferguson → W
- 9c0ae15c07ca5dd6: prop:rec Javonte Williams → W
- b7eb0bec78ac2f5a: prop:rec Kenny Gainwell → W
- 94b634b295a6ccfb: prop:rec Ryan Flournoy → W
- ce844a8a29b01cda: prop:rec Ted Hurst III → V
- f0fc58dcc382abd1: prop:rush_att Bucky Irving → W
- e45496d9dc6776fe: prop:rush_att Javonte Williams → L

### 10 largest-|ln(A/L)| losses (10 rows)

- 87f8829faad48cf8: prop:rec_yds CeeDee Lamb A=9.0 L=82.5 |ln|=2.216
- 42717b625585906e: prop:rec_yds CeeDee Lamb A=9.0 L=82.5 |ln|=2.216
- efdda781e0bf3fea: prop:rec_yds CeeDee Lamb A=9.0 L=82.5 |ln|=2.216
- 2bf4794dde7b831c: prop:rec_yds Tez Johnson A=64.0 L=12.5 |ln|=1.633
- 837d8f0116f88ea4: prop:rec_yds Tez Johnson A=64.0 L=13.5 |ln|=1.556
- fd5e956713551e37: prop:rec_yds Tez Johnson A=64.0 L=13.5 |ln|=1.556
- 489ee832f7c29a09: prop:rec_yds Tez Johnson A=64.0 L=13.5 |ln|=1.556
- 8c3b9b2027cd93da: prop:rec CeeDee Lamb A=2.0 L=6.5 |ln|=1.179
- eb9c28d8929a8d4d: prop:rush_yds Bucky Irving A=165.0 L=52.5 |ln|=1.145
- f594c2f3863c00d4: prop:rush_yds Bucky Irving A=165.0 L=53.5 |ln|=1.126

Total flagged: 102
