# Kalshi Football Series Discovery — 2026-09-20

Source: `GET /trade-api/v2/series?category=Sports`, filtered for "Football"
and "football" in title. Verified from VM (root@142.93.242.4).

## Per-Game Core Series (CAPTURED)

| Ticker         | Title                          | Open Markets | Volume |
|----------------|--------------------------------|-------------|--------|
| KXNFLGAME      | Professional Football Game     | 5+          | Active |
| KXNFLSPREAD    | Pro Football Spread            | 3+          | Active |
| KXNFLTOTAL     | Pro Football Total Points      | 3+          | Active |
| KXNCAAFGAME    | College Football Game          | 3+          | ~0     |
| KXNCAAFSPREAD  | College Football Spread        | 3+          | ~0     |
| KXNCAAFTOTAL   | College Football Total Points  | 3+          | ~0     |

## Per-Game Player Prop Series (FLAGGED, NOT CAPTURED)

These are per-game player props with very few open markets (0-1 each as of
2026-09-20). They include:

NFL: KXNFLTD (touchdowns), KXNFLPASSTDS, KXNFLPASSYDS, KXNFLRSHYDS,
KXNFLRECYDS, KXNFLREC, KXNFLPASSCOMP, KXNFLPASSATT, KXNFLPASSINT,
KXNFLGAMESACK, KXNFLGAMETD, KXNFLFIRSTTD, KXNFLNEXTTD, KXNFLTEAMTD,
KXNFLTEAMFG, KXNFLTEAMTO, KXNFLTEAMSACK, KXNFLTEAMYDS, KXNFLTEAM1STDOWNS,
KXNFLTEAMTOTAL, KXNFL1HTOTAL, KXNFL2HTOTAL, KXNFL1HSPREAD, KXNFL2HSPREAD,
KXNFL1QSPREAD thru KXNFL4QSPREAD, KXNFL1QTOTAL thru KXNFL4QTOTAL,
KXNFL1Q thru KXNFL4Q (quarter winners), KXNFL1HTEAMTOTAL

NCAAF: KXNCAAF1Q thru KXNCAAF4Q, KXNCAAF1QTOTAL thru KXNCAAF4QTOTAL,
KXNCAAF1QSPREAD thru KXNCAAF4QSPREAD, KXNCAAF1HTOTAL, KXNCAAF2HTOTAL,
KXNCAAF1HSPREAD, KXNCAAF2HSPREAD, KXNCAAFTEAMTOTAL, KXNCAAFTEAMTD,
KXNCAAFTEAMFG, KXNCAAFTEAMSACK, KXNCAAFTEAMYDS, KXNCAAFTEAMREC,
KXNCAAFTEAMRECYDS, KXNCAAFTEAMRSHYDS, KXNCAAFTEAMRSHTD, KXNCAAFTEAMRECTD,
KXNCAAFTEAMRSHATT, KXNCAAFTEAMINT, KXNCAAFTEAMTO

Not captured because: (a) hundreds of series with 0-1 open markets each,
(b) most have zero volume, (c) would require hundreds of API calls per cycle.
Can be added later if volume materializes.

## Season-Long Futures (NOT CAPTURED)

KXNFLWINS-*, KXNFLPLAYOFF, KXNFLMVP, KXNFLAFCCHAMP, KXNFLNFCCHAMP,
KXNCAAFPLAYOFF, KXNCAAFCFPPOLL, KXNCAAFWINS, etc.
Out of scope per work order.

## Price Scale

All prices from the REST API are in **dollars** (0.00 to 1.00):
- `yes_bid_dollars`, `yes_ask_dollars`: bid/ask in dollars
- `no_bid_dollars`, `no_ask_dollars`: complement bid/ask
- `last_price_dollars`: last trade price in dollars
- `volume_fp`, `volume_24h_fp`, `open_interest_fp`, `liquidity_dollars`:
  float-point string representations

The WebSocket API (`kalshi_parse_to_parquet.py`) also uses dollar scale
(0.00 to 1.00) for bid/ask/price. Consistent.

## Kickoff Field

`occurrence_datetime` appears to be a kickoff proxy (e.g. 2026-10-04T03:00Z
for a game with close_time 2026-10-06T00:00Z). It is NOT labelled as kickoff
in the API. `close_time` and `expected_expiration_time` are also available.
Pre-game filtering will need the schedule joined on later (see N30).
