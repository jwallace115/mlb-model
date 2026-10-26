# WHY Summary — Week 3

Generated: 2026-10-26T12:10:13.590355+00:00


## Graded rows

- ai_nfl / moneyline / L: 4
- ai_nfl / moneyline / W: 12
- ai_nfl / prop:atd / L: 155
- ai_nfl / prop:atd / V: 39
- ai_nfl / prop:atd / W: 31
- ai_nfl / prop:int / L: 20
- ai_nfl / prop:int / V: 2
- ai_nfl / prop:int / W: 10
- ai_nfl / prop:pass_att / L: 10
- ai_nfl / prop:pass_att / V: 2
- ai_nfl / prop:pass_att / W: 23
- ai_nfl / prop:pass_cmp / L: 19
- ai_nfl / prop:pass_cmp / W: 15
- ai_nfl / prop:pass_td / L: 13
- ai_nfl / prop:pass_td / W: 16
- ai_nfl / prop:pass_yds / L: 14
- ai_nfl / prop:pass_yds / V: 1
- ai_nfl / prop:pass_yds / W: 21
- ai_nfl / prop:rec / L: 72
- ai_nfl / prop:rec / V: 10
- ai_nfl / prop:rec / W: 87
- ai_nfl / prop:rec_yds / L: 73
- ai_nfl / prop:rec_yds / V: 10
- ai_nfl / prop:rec_yds / W: 81
- ai_nfl / prop:rush_att / L: 18
- ai_nfl / prop:rush_att / V: 1
- ai_nfl / prop:rush_att / W: 40
- ai_nfl / prop:rush_yds / L: 37
- ai_nfl / prop:rush_yds / V: 3
- ai_nfl / prop:rush_yds / W: 48
- ai_nfl / spread / L: 5
- ai_nfl / spread / P: 2
- ai_nfl / spread / W: 18
- ai_nfl / total / L: 11
- ai_nfl / total / W: 10
- sim_nfl / prop:atd / L: 4
- sim_nfl / prop:rec / L: 92
- sim_nfl / prop:rec / V: 3
- sim_nfl / prop:rec / W: 90
- sim_nfl / prop:rush_att / L: 25
- sim_nfl / prop:rush_att / W: 21

## why_code_auto (losses)

- EFFICIENCY: 108
- SCRIPT: 77
- SHARE_OTHER: 66
- UNDEFINED: 58
- ROLE_SHIFT: 48
- TURNOVERS: 8
- NOISE: 6
- UNRESOLVED: 4
- NON_OFFENSIVE_TD: 3
- GARBAGE: 2

## why_code_auto (wins)

- EFFICIENCY: 114
- SHARE_OTHER: 100
- SCRIPT: 94
- UNDEFINED: 65
- ROLE_SHIFT: 56
- NOISE: 18
- TURNOVERS: 16
- GARBAGE: 2
- NON_OFFENSIVE_TD: 1

## Thesis verdicts

- thesis_source=none: 284 rows
- thesis_source=nan: 0 rows
- thesis_source=tag_map: 853 rows

## Freeze-join accounting

- Freeze-sourced thesis: 0
- Tag-map thesis: 853
- No thesis: 284

## Unresolved player names (31 rows)

- Jack Bech (4x): markets=['prop:rec_yds', 'prop:rec']
- Josh Oliver (4x): markets=['prop:rec_yds', 'prop:rec']
- Devin Singletary (3x): markets=['prop:rec_yds', 'prop:rec', 'prop:rush_yds']
- Jerry Jeudy (3x): markets=['prop:rec_yds', 'prop:rec']
- Elijah Arroyo (2x): markets=['prop:rec_yds', 'prop:rec']
- Love (2x): markets=['prop:pass_att', 'prop:pass_yds']
- Blake Whiteheart (2x): markets=['prop:rec_yds', 'prop:rec']
- Xavier Legette (2x): markets=['prop:rec_yds', 'prop:rec']
- Adonai Mitchell (2x): markets=['prop:rec_yds', 'prop:rec']
- Adam Trautman (2x): markets=['prop:rec_yds', 'prop:rec']
- Erick All (2x): markets=['prop:rec_yds', 'prop:rec']
- Golden (1x): markets=['prop:rec']
- London (1x): markets=['prop:rec_yds']
- Emari Demercado (1x): markets=['prop:rush_yds']

## PBP vs official stat mismatches (10 rows)

- Penix: prop:pass_att official=25.0 pbp=26.0
- Michael Penix Jr.: prop:pass_att official=25.0 pbp=26.0
- Geno Smith: prop:pass_att official=37.0 pbp=39.0
- Kirk Cousins: prop:pass_att official=33.0 pbp=35.0
- Bo Nix: prop:pass_att official=34.0 pbp=36.0
- Deshaun Watson: prop:pass_att official=30.0 pbp=31.0
- Chuba Hubbard: prop:rush_att official=19.0 pbp=20.0
- Dak Prescott: prop:pass_att official=40.0 pbp=41.0
- Deebo Samuel: prop:rec_yds official=80.0 pbp=0.0
- Chuba Hubbard: prop:rush_att official=19.0 pbp=20.0

## FLAGGED FOR THE TUESDAY READ


### Top 20 picks (60 rows)

- 6496e4cfb0d08b6f: total None → W
- 119d1e953ac17a4d: moneyline None → L
- 97a9105490d09ee9: spread None → W
- e96c38cfacb8607d: moneyline None → W
- cf3bdda78642634b: spread None → W
- 902c9b1fc9be336f: total None → L
- e7bb81995c66cc39: moneyline None → W
- 36fcb7dd1c347c70: spread None → W
- 0d79b8a14dd1eec1: moneyline None → W
- 85b2bcf01293ab10: spread None → W
- 4702ed9736112735: total None → W
- 2b0cd39902be3539: total None → L
- 8b21baca9a6de952: moneyline None → W
- e8b92bf7508774f5: spread None → W
- a5acf92c1e439d5c: total None → L
- 0a1e0c31fa7f65a2: prop:rec Kenyon Sadiq → L
- 7e49f7da2ba6a6aa: prop:rush_att Jahmyr Gibbs → W
- c5a2c07921e576bf: prop:rec Jaylin Noel → W
- 6cb7ea5c92f45278: prop:rec Josh Downs → L
- d5a58b1f99655e67: prop:rec Kayshon Boutte → W
- b9281dc9bca61892: prop:rec Bhayshul Tuten → L
- 5a2f73f38df7a12e: prop:rec Rachaad White → W
- 89dd1b8f69732341: prop:rec Michael Mayer → W
- 8c73b775072e1f52: prop:rec Jaylen Waddle → W
- 1850c6ff07425cb6: prop:rec Rome Odunze → W
- 81a15f9f72f0002a: prop:rush_att Saquon Barkley → L
- e2e39a5d496eb8f7: prop:rec Elic Ayomanor → L
- b86c3eaa7673dc97: prop:rush_att Cam Skattebo → L
- f9822929fb4abcfd: prop:rec Jalen Coker → W
- 37d7ef71fabe8c36: prop:rec Jerry Jeudy → V
- 312de79b83f323c2: prop:rec Ja'Marr Chase → L
- d6cc55800173e5ab: prop:rec Rashod Bateman → W
- abf5390cca66a26a: prop:rush_att Javonte Williams → W
- c9de4b29aa84db9c: prop:rec DJ Moore → L
- 0c14c64c01124c5f: prop:rush_att Aaron Jones → W
- 8d266406f07aa751: prop:rec Chris Olave → L
- 722e098fec1511a8: prop:rec Devaughn Vele → W
- caf2663aa300fbc7: prop:rec Michael Mayer → W
- 5a8de82a45b16bc7: prop:rec Noah Fant → W
- 3c78d4605c05be14: prop:rec Colby Parkinson → W
- a816785e1d056826: prop:rec Davante Adams → L
- c3ad3ca446630108: prop:rec Jaylen Waddle → W
- 3de3a4042089318d: prop:rush_att Blake Corum → W
- 34ca914d764d7104: prop:rec CeeDee Lamb → L
- 68a547f37ff4dcf7: prop:rec George Pickens → L
- dc1d34e490dacfcc: prop:rec Jake Ferguson → W
- cb856cb63f218696: prop:rec Rashod Bateman → W
- 2b6cc0f49319fa7e: prop:rec Ryan Flournoy → W
- 6e9c62f3e4056422: prop:rush_att Derrick Henry → W
- f65a679a868a90f2: prop:rush_att Javonte Williams → W
- a4c0ff83af01a45d: prop:rec Jalen McMillan → L
- 2d413f9533c05dd5: prop:rec Jauan Jennings → L
- b6fa671ec53ef3e7: prop:rec Josh Oliver → L
- e39fb03c0bc13527: prop:rush_att Aaron Jones → W
- 30e393aae65b911f: prop:rush_att Bucky Irving → L
- 3248d8bdf7d9a3d4: spread None → W
- 66ab1ae01f9c1781: spread None → L
- fcb227a1b6d0764f: spread None → L
- c84b8a0136499b69: spread None → P
- c720622a74a84d44: spread None → W

### 10 largest-|ln(A/L)| losses (10 rows)

- d80359fd52c81055: prop:rush_yds Kenny Gainwell A=-4.0 L=18.5 |ln|=7.523
- 788a05213f94518c: prop:rec_yds Bryce Lance A=0.0 L=15.5 |ln|=7.346
- ad433219b930e8ae: prop:rec_yds Calvin Ridley A=0.0 L=14.5 |ln|=7.279
- 07534c82b462b8cb: prop:rec_yds Jalen McMillan A=0.0 L=14.5 |ln|=7.279
- 8af61fc351802ed5: prop:rec_yds Drew Sample A=0.0 L=6.5 |ln|=6.477
- 7896bb3da2f99336: prop:rush_yds KC Concepcion A=0.0 L=4.5 |ln|=6.109
- 829f38bcdda1d1e3: prop:rec De'Von Achane A=0.0 L=3.5 |ln|=5.858
- dcf2f619af7ecd55: prop:rec Evan Engram A=0.0 L=2.5 |ln|=5.521
- 434c1d292f7478ae: prop:rec Evan Engram A=0.0 L=2.5 |ln|=5.521
- 4e20961ad54bc2b2: prop:rec Bryce Lance A=0.0 L=1.5 |ln|=5.011

### AVAILABILITY / ROLE_SHIFT (104 rows)

- 0348034a3ff31e51: ROLE_SHIFT prop:rec_yds Chris Bell
- 46fee4207879951c: ROLE_SHIFT prop:rec_yds Greg Dulcich
- 7abada25815c0a1c: ROLE_SHIFT prop:rec Chris Bell
- 55b2adcc02f2cace: ROLE_SHIFT prop:rec Greg Dulcich
- 8967dfbbfa6c1419: ROLE_SHIFT prop:rec Malik Washington
- 3561494df9770e84: ROLE_SHIFT prop:rec_yds Breece Hall
- fa9ecce5f3ad4741: ROLE_SHIFT prop:rec_yds Garrett Wilson
- f120cb777947c6dd: ROLE_SHIFT prop:rec_yds Isaiah Williams
- 84a317451201b36a: ROLE_SHIFT prop:rec_yds Jeremy Ruckert
- ff1f06fe2d47da25: ROLE_SHIFT prop:rec Breece Hall
- 6ca43b9d7dd1cee3: ROLE_SHIFT prop:rec Garrett Wilson
- 01d1d7f162f76966: ROLE_SHIFT prop:rec Jeremy Ruckert
- 3a4a16dbea992fb6: ROLE_SHIFT prop:rec Kenyon Sadiq
- 9974359d761756cf: ROLE_SHIFT prop:rec_yds Dalton Schultz
- 2568cadc20d3dc1d: ROLE_SHIFT prop:rec_yds Jared Wayne
- 198d624f3355c463: ROLE_SHIFT prop:rec_yds Josh Downs
- 82ff7f2c9fb527e4: ROLE_SHIFT prop:rec_yds Laquon Treadwell
- 4bb7a96f6c0ab2ef: ROLE_SHIFT prop:rec Dalton Schultz
- 2fffe7fff0da925a: ROLE_SHIFT prop:rec Jonathan Taylor
- fcaca85b1ace1fc6: ROLE_SHIFT prop:rec Keenan Allen
- 285a2f805a011a7b: ROLE_SHIFT prop:rec Laquon Treadwell
- a5c1094561ce99ff: ROLE_SHIFT prop:rec Tyler Warren
- 9671c0034f179d30: ROLE_SHIFT prop:rec Woody Marks
- 2da0a9a6aa9772cf: ROLE_SHIFT prop:pass_att Drake Maye
- 52123a7d7777f73d: ROLE_SHIFT prop:pass_cmp Drake Maye
- fc0a63289f5983fe: ROLE_SHIFT prop:pass_yds Drake Maye
- 4fd989ff7141f450: ROLE_SHIFT prop:rec_yds Bhayshul Tuten
- 4b22857d5940c913: ROLE_SHIFT prop:rec_yds Brenton Strange
- 1d80d28731b1d81b: ROLE_SHIFT prop:rec_yds Brian Thomas Jr
- 7ec7e1813f3ff5cd: ROLE_SHIFT prop:rec_yds Jakobi Meyers
- c467f424fd304e80: ROLE_SHIFT prop:rec_yds Mack Hollins
- a784a0e4f1cbf27c: ROLE_SHIFT prop:rec_yds Parker Washington
- ee79899ea7acbd11: ROLE_SHIFT prop:rec_yds Rhamondre Stevenson
- 20ecdaf9fe9493c8: ROLE_SHIFT prop:rec Bhayshul Tuten
- 14edf0093c7c0dea: ROLE_SHIFT prop:rec Brenton Strange
- 9fa032339e8a3f6f: ROLE_SHIFT prop:rec Brian Thomas Jr
- 87cb90798a0cd8fb: ROLE_SHIFT prop:rec Hunter Henry
- 68916676919f7c71: ROLE_SHIFT prop:rec Jakobi Meyers
- 089ac39c086df8f4: ROLE_SHIFT prop:rec Mack Hollins
- 8bb2e7b7b3434c61: ROLE_SHIFT prop:rec Parker Washington
- 0e578005938547fd: ROLE_SHIFT prop:rec_yds Rachaad White
- c3cb0954e7c95e4a: ROLE_SHIFT prop:rec Rachaad White
- 1d274552b82cdbf5: ROLE_SHIFT prop:rec_yds Terrance Ferguson
- 94ec243b9992a31c: ROLE_SHIFT prop:rec Terrance Ferguson
- 1c164852b915024f: ROLE_SHIFT prop:rush_att Bo Nix
- abe15e6b9533fa3f: ROLE_SHIFT prop:rush_att J.K. Dobbins
- d7819f3d2337e3af: ROLE_SHIFT prop:rush_yds J.K. Dobbins
- 2492186587ac06f7: ROLE_SHIFT prop:rec_yds Darren Waller
- 1e4c850f1670e7af: ROLE_SHIFT prop:rec_yds Jalen Coker
- 50116963401c407a: ROLE_SHIFT prop:rec Darren Waller
- 05ac8ef47d931276: ROLE_SHIFT prop:rec Jalen Coker
- 2256d4cffdbd9717: ROLE_SHIFT prop:rec Tetairoa McMillan
- 552d77c990e0a309: ROLE_SHIFT prop:rush_att Chuba Hubbard
- 2a54ecec276a6c48: ROLE_SHIFT prop:rush_yds Chuba Hubbard
- c65744f64cbc6ced: ROLE_SHIFT prop:rec_yds Chase Brown
- 50b650f390db41c1: ROLE_SHIFT prop:rec_yds Ja'Marr Chase
- 73a8cbe12927ea36: ROLE_SHIFT prop:rec Chase Brown
- 9f85afa5039a62c1: ROLE_SHIFT prop:rec Ja'Marr Chase
- f82c67480d893674: ROLE_SHIFT prop:rush_att Jaylen Warren
- a6ef91f81f37534b: ROLE_SHIFT prop:rec_yds George Kittle
- f5889ec0dc38a79e: ROLE_SHIFT prop:rec George Kittle
- 5c9ae799d4cdec90: ROLE_SHIFT prop:rush_att Christian McCaffrey
- 3b5b56e1728c8193: ROLE_SHIFT prop:rush_yds Christian McCaffrey
- aa6031b3f539ef93: ROLE_SHIFT prop:rush_yds Kaelon Black
- 29c973337859d552: ROLE_SHIFT prop:rec_yds Ladd McConkey
- 61b1976c02e91948: ROLE_SHIFT prop:rec_yds Tre Harris
- 9ba2e3635fb7846b: ROLE_SHIFT prop:rec Ladd McConkey
- d8ec27a4968e610d: ROLE_SHIFT prop:rush_att James Cook
- 837072b408ceb327: ROLE_SHIFT prop:rush_att Josh Allen
- 32d58381d44dbedd: ROLE_SHIFT prop:rush_yds James Cook
- e1d7d2c0018ef0f8: ROLE_SHIFT prop:rec Chris Bell
- cdf033d853bc730e: ROLE_SHIFT prop:rec Greg Dulcich
- df3910c704d7600a: ROLE_SHIFT prop:rec Malik Washington
- ec39e1c00719a6e0: ROLE_SHIFT prop:rec Breece Hall
- 2a4cd608e3b4ecd6: ROLE_SHIFT prop:rec Garrett Wilson
- 0a1e0c31fa7f65a2: ROLE_SHIFT prop:rec Kenyon Sadiq
- 3794f16b19ff8ce3: ROLE_SHIFT prop:rec Dalton Schultz
- 4aae265ff5452625: ROLE_SHIFT prop:rec Jonathan Taylor
- 5c48b8c2384960a1: ROLE_SHIFT prop:rec Keenan Allen
- 4dfa07a594747f30: ROLE_SHIFT prop:rec Tyler Warren
- 41627c94c70ea047: ROLE_SHIFT prop:rec Woody Marks
- b9281dc9bca61892: ROLE_SHIFT prop:rec Bhayshul Tuten
- 83e9856329e54e27: ROLE_SHIFT prop:rec Brenton Strange
- 566051cf45ae6131: ROLE_SHIFT prop:rec Hunter Henry
- b74920621869a517: ROLE_SHIFT prop:rec Jakobi Meyers
- c83df3149df1fdf0: ROLE_SHIFT prop:rec Mack Hollins
- de5d0e0cffb99f88: ROLE_SHIFT prop:rec Parker Washington
- 5a2f73f38df7a12e: ROLE_SHIFT prop:rec Rachaad White
- 614e6b397646f61c: ROLE_SHIFT prop:rush_att J.K. Dobbins
- 342f47525105da43: ROLE_SHIFT prop:rec Makai Lemon
- a043dbc6a516808f: ROLE_SHIFT prop:rec Darren Waller
- f9822929fb4abcfd: ROLE_SHIFT prop:rec Jalen Coker
- e7fd10fe02e27028: ROLE_SHIFT prop:rec Tetairoa McMillan
- b803eb5e77d5a8be: ROLE_SHIFT prop:rush_att Chuba Hubbard
- 58b22d8c4a84614d: ROLE_SHIFT prop:rec Chase Brown
- 312de79b83f323c2: ROLE_SHIFT prop:rec Ja'Marr Chase
- fdd55e8768169302: ROLE_SHIFT prop:rush_att Jaylen Warren
- b7293abc09cadb70: ROLE_SHIFT prop:rec George Kittle
- d6d3f76e62a7201c: ROLE_SHIFT prop:rush_att Christian McCaffrey
- 7310ab82d018756f: ROLE_SHIFT prop:rec Ladd McConkey
- cad5236906aff0f9: ROLE_SHIFT prop:rush_att James Cook
- 35b1dda1a1df36f9: ROLE_SHIFT prop:rush_att J.K. Dobbins
- 426e85282d3622df: ROLE_SHIFT prop:rec George Kittle
- 79ef27fe1a28a4fc: ROLE_SHIFT prop:rush_att Christian McCaffrey

Total flagged: 174
