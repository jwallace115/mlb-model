# site/tickets — AI parlay cards shown on the Today page

One JSON file per card, written when the card is sent (append-only: a revised card is a new file).
File name: `<slate_date>_<ticket>.json`, e.g. `2026-10-04_SUN_LINES_5.json`.

```json
{
  "ticket": "Sunday lines 5-leg",
  "slate_date": "2026-10-04",
  "logged_utc": "2026-10-04T16:12Z",
  "prices_from": "hardrockbet_fl 16:05Z props pull",
  "legs": [
    {"leg": "PIT -2.5", "game": "PIT @ CLE", "price": -120, "why": "One short reason in the reader's words."}
  ]
}
```

`price` is the play-down-to price (that price or better, bet it). No stakes, slip ids or account
details ever go in these files — the repo is public.
