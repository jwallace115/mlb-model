# WHY Summary — Week 6

Generated: 2026-10-18T11:13:44.600677+00:00


## Graded rows

- ai_nfl / moneyline / W: 2
- ai_nfl / prop:atd / L: 4
- ai_nfl / prop:atd / V: 2
- ai_nfl / prop:atd / W: 1
- ai_nfl / prop:int / L: 1
- ai_nfl / prop:int / W: 3
- ai_nfl / prop:pass_att / L: 2
- ai_nfl / prop:pass_att / W: 2
- ai_nfl / prop:pass_cmp / L: 2
- ai_nfl / prop:pass_cmp / W: 2
- ai_nfl / prop:pass_td / W: 4
- ai_nfl / prop:pass_yds / L: 2
- ai_nfl / prop:pass_yds / W: 4
- ai_nfl / prop:rec / L: 12
- ai_nfl / prop:rec / V: 1
- ai_nfl / prop:rec / W: 17
- ai_nfl / prop:rec_yds / L: 10
- ai_nfl / prop:rec_yds / V: 1
- ai_nfl / prop:rec_yds / W: 17
- ai_nfl / prop:rush_att / L: 4
- ai_nfl / prop:rush_att / W: 5
- ai_nfl / prop:rush_yds / L: 6
- ai_nfl / prop:rush_yds / W: 9
- ai_nfl / spread / L: 1
- ai_nfl / spread / W: 2
- ai_nfl / total / L: 1
- ai_nfl / total / W: 1
- sim_nfl / prop:rec / L: 4
- sim_nfl / prop:rec / W: 8
- sim_nfl / prop:rush_att / L: 1
- sim_nfl / prop:rush_att / W: 2

## why_code_auto (losses)

- EFFICIENCY: 13
- SCRIPT: 11
- ROLE_SHIFT: 11
- SHARE_OTHER: 7
- TURNOVERS: 2
- UNDEFINED: 1

## why_code_auto (wins)

- SCRIPT: 23
- EFFICIENCY: 21
- UNDEFINED: 10
- ROLE_SHIFT: 9
- TURNOVERS: 3
- SHARE_OTHER: 3
- NOISE: 2

## Thesis verdicts

- thesis_source=freeze: 116 rows
- thesis_source=none: 15 rows
- thesis_source=nan: 0 rows

## Freeze-join accounting

- Freeze-sourced thesis: 116
- Tag-map thesis: 0
- No thesis: 15

## Unresolved player names (2 rows)

- Lil'Jordan Humphrey (2x): markets=['prop:rec_yds', 'prop:rec']

## PBP vs official stat mismatches (2 rows)

- Sam Darnold: prop:pass_att official=51.0 pbp=52.0
- Sam Darnold: prop:pass_att official=51.0 pbp=52.0

## FLAGGED FOR THE TUESDAY READ


### Top 20 picks (47 rows)

- b04f1a069fea8c07: prop:pass_cmp Sam Darnold → L
- c8a18dc45e93ef1d: prop:rush_yds Bo Nix → W
- ff8a4f18b2a029b3: prop:rec AJ Barner → W
- c9d5ecedd2fb2889: prop:rec Cooper Kupp → W
- 4fcaac95be46b371: prop:rec Courtland Sutton → L
- e9f28f00c2b563a5: prop:rec Emanuel Wilson → W
- 02192f376f5a7764: prop:rec Evan Engram → W
- 99acf571bdb7fea8: prop:rec George Holani → W
- e26b1df677cad53d: prop:rec J.K. Dobbins → L
- 3d00faaa44ab1902: prop:rec Jaxon Smith-Njigba → L
- 3db7ec9862f8b2d2: prop:rec Jaylen Waddle → L
- a08397d7be10ebbb: prop:rec RJ Harvey → W
- 961f04cdb6026221: prop:rec Rashid Shaheed → W
- 648d5b35d1aa56e0: prop:rec Troy Franklin → W
- 08d3c007ff61d46e: prop:rush_att Emanuel Wilson → W
- 97d5cf8be3e5db9c: prop:rush_att J.K. Dobbins → W
- fece1532c9f9a66c: prop:rush_att RJ Harvey → L
- 41b40475ec81fd97: prop:pass_yds Bo Nix → W
- a11d58e9b4a64ae6: prop:pass_yds Sam Darnold → W
- bb886bc182117997: prop:rec_yds Jaxon Smith-Njigba → W
- 8a9d728fe4c3b9f4: prop:rec Evan Engram → W
- 607a307d70024c26: prop:rec Rashid Shaheed → W
- 2f936d65a37911ee: prop:rec Troy Franklin → W
- 48ba8f5aa23bf1d9: prop:rush_att Emanuel Wilson → L
- 950d05fc41a6b62a: prop:rush_att J.K. Dobbins → W
- 042854a20cc38380: prop:rush_yds J.K. Dobbins → L
- 48af79ffe3822cb7: spread None → L
- 66880dddf369a374: moneyline None → W
- 4b568d2445ae26e6: prop:atd Adam Prentice → L
- 52a35edb141ff484: prop:pass_cmp Bo Nix → W
- f8ccc143fe9586b8: prop:pass_td Bo Nix → W
- f8ab07afac238af0: prop:pass_td Sam Darnold → W
- f4b3bdba746db8fd: prop:rec_yds Cooper Kupp → L
- 2bc6b7d7dab60e2d: prop:rec_yds Emanuel Wilson → W
- f0a6098e5366b203: prop:rec_yds George Holani → W
- 2310611715e2c404: prop:rec_yds RJ Harvey → L
- ea92b7ce5537f6f8: prop:rec_yds Troy Franklin → W
- 1e80f9b0d58d9c0f: prop:rec Evan Engram → W
- 7449e59add4dc1ed: prop:rec George Holani → W
- 84f95608d182e709: prop:rec Jaxon Smith-Njigba → L
- e286cef4c9473012: prop:rec Jaylen Waddle → L
- ba1a1250258b95a2: prop:rec Marvin Mims Jr. → W
- b7c7f30bdb695751: prop:rec RJ Harvey → W
- e07335ad48698319: prop:rec Rashid Shaheed → W
- 90ce539cc3c92ce3: prop:rec Troy Franklin → L
- 76657876f668114c: prop:rush_yds Emanuel Wilson → W
- e0f1e941e274cc7f: spread None → W

### 10 largest-|ln(A/L)| losses (10 rows)

- b12a7415b6735352: prop:rush_yds Jaxon Smith-Njigba A=0.0 L=0.5 |ln|=3.912
- 115a66e11d513961: prop:rush_yds Sam Darnold A=19.0 L=4.5 |ln|=1.440
- d3d2a0060eaec09a: prop:rush_yds Sam Darnold A=19.0 L=4.5 |ln|=1.440
- 3d74897000c8b5cf: prop:rush_yds Rashid Shaheed A=2.0 L=0.5 |ln|=1.386
- 1f600dd5fdb990ff: prop:rec_yds Rashid Shaheed A=66.0 L=22.5 |ln|=1.076
- 39cd0afedf28b9cb: prop:rec_yds Tory Horton A=13.0 L=4.5 |ln|=1.061
- b6c0a6e5db5d43df: prop:rec_yds Cooper Kupp A=50.0 L=20.5 |ln|=0.892
- f4b3bdba746db8fd: prop:rec_yds Cooper Kupp A=50.0 L=21.5 |ln|=0.844
- 9fbc874b7347c56f: prop:rec Cooper Kupp A=5.0 L=2.5 |ln|=0.693
- e26b1df677cad53d: prop:rec J.K. Dobbins A=3.0 L=1.5 |ln|=0.693

### AVAILABILITY / ROLE_SHIFT (20 rows)

- 78e3345fea9a2ff8: ROLE_SHIFT prop:rec_yds Evan Engram
- f79f005d7e7a7e84: ROLE_SHIFT prop:rec_yds Marvin Mims Jr.
- 59d190b893f4b403: ROLE_SHIFT prop:rec Courtland Sutton
- a73972cccd1e5fee: ROLE_SHIFT prop:rec Jaylen Waddle
- df95216eae99ba42: ROLE_SHIFT prop:rec Marvin Mims Jr.
- 79a66e067e7d8780: ROLE_SHIFT prop:rush_yds RJ Harvey
- 4fcaac95be46b371: ROLE_SHIFT prop:rec Courtland Sutton
- e26b1df677cad53d: ROLE_SHIFT prop:rec J.K. Dobbins
- 3db7ec9862f8b2d2: ROLE_SHIFT prop:rec Jaylen Waddle
- fece1532c9f9a66c: ROLE_SHIFT prop:rush_att RJ Harvey
- 9e835f77bfd81e85: ROLE_SHIFT prop:rec_yds Evan Engram
- 46f8eb9172d7e7d2: ROLE_SHIFT prop:rec_yds J.K. Dobbins
- 350800cdb8408cef: ROLE_SHIFT prop:rec_yds Marvin Mims Jr.
- 68af6e03cfb790d9: ROLE_SHIFT prop:rec Courtland Sutton
- 4aeb194402716f63: ROLE_SHIFT prop:rec J.K. Dobbins
- e286cef4c9473012: ROLE_SHIFT prop:rec Jaylen Waddle
- ba1a1250258b95a2: ROLE_SHIFT prop:rec Marvin Mims Jr.
- d5164c69b2a2d21a: ROLE_SHIFT prop:rush_att RJ Harvey
- b6edb75c5f16b73c: ROLE_SHIFT prop:rush_att Sam Darnold
- b319a70eb10dd92a: ROLE_SHIFT prop:rush_yds RJ Harvey

Total flagged: 77
