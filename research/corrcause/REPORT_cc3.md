# CC-3 Report: Is the NHL divergence-under survivor a stale-quote artefact?

## Summary

T2_NHL_f1_divergence_flag_yes_under (n=592, r=+0.068, p=0.00044) survived BH in the
CC-2 screen. Cowork identified that `extract_closes` takes each book's last pre-tip
snapshot independently, so "divergence at close" could compare quotes hours apart.
CC-3 measures both the asynchrony and the under excess in synchronous, fresh quotes.

---

## Item 1: What the flag actually is

### Flag anatomy (2,638 NHL DEV games, 2,634 with Pinnacle close)

v2 flag fires on 637 games (24.1%). Synchronous re-flag (same snapshot as Pinnacle,
book_last_update age <= 10 min) fires on 602 games (22.8%).

### Driving-book gap distribution (flagged games, n=637)

| Gap range | Count | Share |
|---|---|---|
| 0 min (same snapshot) | 602 | 0.945 |
| >0 to <=10 min | 5 | 0.008 |
| >10 to <=60 min | 3 | 0.005 |
| >60 min | 27 | 0.042 |

94.5% of flagged games have the driving book quoting in the **exact same API snapshot**
as Pinnacle. Driving-book `book_last_update` age: median 0.6 min, 0% > 30 min.

### Per-book same-snapshot rates (all games)

| Book | In Pinnacle snap | Share |
|---|---|---|
| williamhill_us | 2633/2638 | 1.000 |
| betonlineag | 2629/2638 | 0.998 |
| betmgm | 2627/2638 | 0.997 |
| draftkings | 2619/2638 | 0.994 |
| fanduel | 2611/2638 | 0.994 |
| pointsbetus | 2595/2638 | 0.986 |
| bovada | 2552/2638 | 0.973 |
| betrivers | 2524/2638 | 0.958 |

### Driving book distribution (flagged games)

| Book | Count | Share |
|---|---|---|
| betmgm | 148 | 0.232 |
| pointsbetus | 117 | 0.184 |
| betrivers | 91 | 0.143 |
| fanduel | 73 | 0.115 |
| unibet_us | 63 | 0.099 |
| williamhill_us | 50 | 0.078 |
| bovada | 46 | 0.072 |
| draftkings | 38 | 0.060 |
| betonlineag | 11 | 0.017 |

Sign of divergence: soft higher on home 305 (47.9%), soft lower 332 (52.1%).
Approximately balanced.

### Pinnacle ML move last 3h (all games, prob pts)

Mean: -0.001, std: 0.015, median: 0.000.

### Pinnacle total move last 3h (all games, points)

Mean: -0.012, std: 0.215, median: 0.000.

### Null control

Games where ALL soft books quote in Pinnacle's last snapshot (n>=3 books): 2,416.
sync_flag agrees with v2_flag: **99.8%** (threshold: >= 90%). **PASS.**

```
sync_flag   0.0  1.0   All
v2_flag
0.0        1857    0  1857
1.0           6  553   559
All        1863  553  2416
```

v2 flagged AND sync flagged: 602
v2 flagged BUT NOT sync flagged: 35
NOT v2 flagged BUT sync flagged: 0

---

## Item 2: Where the under excess lives

### Population base

| Season | n | mean under_resid | SE |
|---|---|---|---|
| ALL | 2454 | +0.0221 | 0.0101 |
| 2022-23 | 1218 | +0.0160 | 0.0143 |
| 2023-24 | 1236 | +0.0280 | 0.0142 |

### (a) v2 flag x driving-book quote age

| Cut | n | mean | SE |
|---|---|---|---|
| flag=yes, drv_age <=10m (pooled) | 576 | +0.0732 | 0.0206 |
| flag=yes, drv_age <=10m (2022-23) | 256 | +0.0925 | 0.0307 |
| flag=yes, drv_age <=10m (2023-24) | 320 | +0.0577 | 0.0278 |
| flag=yes, drv_age 10-60m (pooled) | 16 | -0.1155 | 0.1266 |
| flag=no (all) (pooled) | 1862 | +0.0075 | 0.0116 |
| flag=no (all) (2022-23) | 962 | -0.0043 | 0.0161 |
| flag=no (all) (2023-24) | 900 | +0.0201 | 0.0167 |

The under excess in flagged games lives entirely in fresh quotes (drv_age <=10m).
The 16 stale flagged games are negative. 0 games have drv_age > 60m.

### (b) SYNCHRONOUS flag yes/no -- THE KEY ROW

| Cut | n | mean | SE |
|---|---|---|---|
| **sync_flag=yes (pooled)** | **558** | **+0.0683** | **0.0210** |
| sync_flag=yes (2022-23) | 233 | +0.0868 | 0.0323 |
| sync_flag=yes (2023-24) | 325 | +0.0550 | 0.0276 |
| sync_flag=no (pooled) | 1896 | +0.0085 | 0.0115 |
| sync_flag=no (2022-23) | 985 | -0.0007 | 0.0159 |
| sync_flag=no (2023-24) | 911 | +0.0184 | 0.0166 |

Synchronous-flag under residual: **+0.068 over Pinnacle fair** (SE 0.021), which is
**+0.046 over the population base** (+0.022). Present in both seasons.

### (c) v2 flag x sign of divergence

| Cut | n | mean | SE |
|---|---|---|---|
| flag=yes, soft higher on home (pooled) | 286 | +0.0732 | 0.0293 |
| flag=yes, soft lower on home (pooled) | 306 | +0.0633 | 0.0283 |
| flag=no (pooled) | 1862 | +0.0075 | 0.0116 |

Both sign directions carry the excess. Not a directional artefact.

### (d) By driving book (flagged games, pooled)

| Book | n | mean | SE |
|---|---|---|---|
| betonlineag | 11 | +0.2316 | 0.1420 |
| bovada | 43 | +0.1314 | 0.0744 |
| williamhill_us | 45 | +0.1035 | 0.0729 |
| fanduel | 65 | +0.1053 | 0.0612 |
| betmgm | 138 | +0.0878 | 0.0417 |
| draftkings | 34 | +0.0605 | 0.0870 |
| unibet_us | 61 | +0.0445 | 0.0650 |
| betrivers | 86 | +0.0415 | 0.0543 |
| pointsbetus | 109 | +0.0014 | 0.0481 |

Distributed across books. pointsbetus is the only near-zero.

### (e) Pinnacle last-3h moves x flag (pooled)

| ML move bin | flag=yes | flag=no |
|---|---|---|
| <1pt | +0.064 (n=301) | +0.014 (n=1239) |
| 1-3pt | +0.069 (n=234) | -0.002 (n=523) |
| >=3pt | +0.083 (n=57) | -0.028 (n=100) |

| Total move | flag=yes | flag=no |
|---|---|---|
| down | +0.098 (n=49) | +0.010 (n=187) |
| flat | +0.063 (n=513) | +0.004 (n=1523) |
| up | +0.108 (n=30) | +0.036 (n=152) |

The under excess is stable across ML move bins. It does NOT track late Pinnacle ML moves.
The flag=yes effect is present whether Pinnacle moved <1pt or >=3pt.

### (f) v2 flag x backup goalie

Share of backup-goalie games: flag=yes **0.318**, flag=no **0.322** (identical).

| Cut | n | mean | SE |
|---|---|---|---|
| flag=yes, backup=yes (pooled) | 188 | +0.0907 | 0.0359 |
| flag=yes, backup=no (pooled) | 404 | +0.0575 | 0.0247 |
| flag=no, backup=yes (pooled) | 600 | +0.0129 | 0.0205 |
| flag=no, backup=no (pooled) | 1262 | +0.0049 | 0.0141 |

Backup games are NOT over-represented in flagged games (32% vs 32%). The under
excess is present in BOTH backup and primary starts. Backup-flagged is stronger
(+0.091) but primary-flagged is still +0.058, well above the population base.

### (g) By month

| Month | flag=yes n | flag=yes mean | flag=no n | flag=no mean |
|---|---|---|---|---|
| 1 | 82 | -0.059 | 319 | +0.047 |
| 2 | 53 | +0.104 | 249 | +0.007 |
| 3 | 124 | +0.102 | 324 | -0.012 |
| 4 | 63 | +0.028 | 163 | -0.019 |
| 10 | 68 | +0.093 | 199 | +0.023 |
| 11 | 108 | +0.090 | 283 | +0.005 |
| 12 | 94 | +0.097 | 325 | -0.005 |

January is the one negative month for flagged games. No month carries > 21% of the
sample. Six of seven months are positive for flag=yes.

### (h) ROI at best same-snapshot soft under price

| Measure | n | ROI | SE |
|---|---|---|---|
| Sync soft best under | 551 | +0.1057 | 0.0418 |
| v2 soft best under | 585 | +0.1057 | 0.0406 |

### Positive-control sanity

Home ML residual (synchronous rows): mean = **-0.003** (SE 0.020, n=558).
Within +/-0.01: **YES**.

---

## What the numbers mean

### Is the v2 flag mostly asynchronous?

**No.** 94.5% of flagged games have the driving book quoting in the exact same API
snapshot as Pinnacle, with book_last_update age median 0.6 min. The asynchronous-quote
hypothesis is dead: the divergence is a genuine price disagreement in real-time quotes.
Only 27/637 flagged games (4.2%) have driving-book gaps > 60 min, and 0 have driving-book
`book_last_update` > 30 min.

### Does the under excess survive in synchronous fresh rows and by how much over the population base?

**Yes.** Synchronous-flag under residual = +0.068 (SE 0.021), which is **+0.046 over the
population base** of +0.022. Present in both DEV seasons (2022: +0.087, 2023: +0.055).
ROI at best sync soft under price: +10.6% (SE 4.2%, n=551).

### Does it track late Pinnacle ML moves and/or backup starts?

**Neither.** The under excess is stable across ML move bins (<1pt: +0.064, 1-3pt: +0.069,
>=3pt: +0.083 for flag=yes vs +0.014/-0.002/-0.028 for flag=no). Backup goalie share is
identical in flagged vs unflagged groups (32% vs 32%). The effect is present in both backup
and primary starts.

---

## NOT DONE

- No mechanism proposed (per work order: no mechanism, no Q, no CONFIRM in this order)
- No OOS test (2024-25 and 2025-26 data not read)
- No investigation of WHY soft books diverge from Pinnacle on these games
- January negative month not explained

## UNVERIFIED

- Whether the population under base (+0.022) itself is an artefact of the close-price
  extraction method or a genuine market feature
- Whether the sync-flag definition (blu_age <= 10 min) is the right freshness threshold
  (not tested at 5 min or 2 min)
- Whether the per-book driving distribution (betmgm leading at 23%) reflects model
  differences or liquidity differences
- Whether the ROI survives transaction costs and execution slippage at the listed books
