# CC-3 Item 1: Flag Anatomy

Total games: 2638

Games with Pinnacle close: 2634

v2 flag=yes: 637, flag=no: 1997

Sync-eligible games (>=1 book in Pinnacle snap with blu<=10m): 2634
Sync flag=yes: 602, sync flag=no: 2032

## Driving-book gap distribution (flagged games, n=637)

| Gap range | Count | Share |
|---|---|---|
| 0 min (same snapshot) | 602 | 0.945 |
| >0 to <=10 min | 5 | 0.008 |
| >10 to <=60 min | 3 | 0.005 |
| >60 min | 27 | 0.042 |

| Metric | Flagged (n=637) | Unflagged (n=1997) |
|---|---|---|
| Driving-book gap median | 0.0 min | -- |
| Driving-book gap p90 | 0.0 min | -- |
| Share gap > 60 min | 0.042 | -- |
| Driving-book blu age median | 0.6 min | -- |
| Share driving-book blu > 30 min | 0.000 | -- |

## Pinnacle close age

| Metric | Flagged (n=637) | Unflagged (n=1997) |
|---|---|---|
| Flagged pin close age median | 4.3 min | |
| Unflagged pin close age median | 4.3 min | |

## Driving book distribution (flagged games)

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

## Sign of divergence (flagged games)

Soft higher on home: 305 (0.479)
Soft lower on home: 332 (0.521)

## Per-book same-snapshot rates (all games)

| Book | In Pinnacle snap | Share |
|---|---|---|
| williamhill_us | 2633/2638 | 1.000 |
| unibet_us | 2594/2638 | 0.999 |
| betonlineag | 2629/2638 | 0.998 |
| betmgm | 2627/2638 | 0.997 |
| draftkings | 2619/2638 | 0.994 |
| fanduel | 2611/2638 | 0.994 |
| pointsbetus | 2595/2638 | 0.986 |
| bovada | 2552/2638 | 0.973 |
| betrivers | 2524/2638 | 0.958 |

## Pinnacle ML move last 3h (all games, prob pts)

| Stat | Value |
|---|---|
| mean | -0.001 |
| std | 0.015 |
| min | -0.070 |
| 25% | -0.007 |
| median | 0.000 |
| 75% | 0.006 |
| max | 0.128 |

## Pinnacle total move last 3h (all games, points)

| Stat | Value |
|---|---|
| mean | -0.012 |
| std | 0.215 |
| median | 0.000 |

## Null control: sync flag vs v2 flag (all books in same snapshot)

Games where ALL soft books quote in Pinnacle's last snapshot (n>=3 books): 2416
Agreement: 0.998 (99.8%)

```
sync_flag   0.0  1.0   All
v2_flag
0.0        1857    0  1857
1.0           6  553   559
All        1863  553  2416
```

6 games are v2-flagged but NOT sync-flagged in the all-same-snapshot set. These are cases
where the divergent book's book_last_update age exceeded 10 min despite appearing in the
same API snapshot.

## Summary statistics

| Metric | Value |
|---|---|
| Total games | 2638 |
| With Pinnacle close | 2634 |
| v2 flagged | 637 (0.241) |
| Sync-eligible | 2634 |
| Sync flagged | 602 (0.228) |
| v2 flagged AND sync flagged | 602 |
| v2 flagged BUT NOT sync flagged | 35 |
| NOT v2 flagged BUT sync flagged | 0 |
