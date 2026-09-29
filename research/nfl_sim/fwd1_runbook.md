# FWD1 Runbook — NFL sim v1 forward test, week 4 commands

Reader model: `nfl_sim_v1_156cd057`

## Week 4 kick windows

### TNF PIT@CLE — Thu 2026-10-02 00:15Z (Thu 8:15 PM ET)

```bash
python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 2
```

Run at **23:30Z Thu 10-01** (7:30 PM ET).
Newest HR props pull: the VM's Thu 22:00Z slot (~1.5 h old). OK.

### London IND@WAS — Sun 2026-10-04 13:30Z (9:30 AM ET)

```bash
python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 1.5
```

Run at **12:45Z Sun 10-04** (8:45 AM ET).
Newest HR props pull: the VM's Sat 14:00Z mid slot (~23 h old) — there is no Sunday slot before 15:00Z.
The sim and the book are compared at the same (stale) price, so the forward test stays fair; the prices are
not what Hard Rock shows at kick. The file records `source_age_min`.

### Sunday 1 PM + 4 PM + SNF — Sun 2026-10-04 17:00Z / 20:05Z / 20:25Z / Mon 00:20Z

```bash
python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 9
```

Run at **16:15Z Sun 10-04** (12:15 PM ET).
Newest HR props pull: ~16:00Z (15 min old). OK.
The 9-hour window covers 17:00Z through 01:15Z, capturing all Sunday and SNF games.

### MNF — Mon 2026-10-06 00:15Z+ (Mon 8:15 PM ET)

```bash
python3 nfl/sim/run_forward_v1.py --week 4 --window-hours 2
```

Run at **23:55Z Mon 10-05** (7:55 PM ET) — AFTER the VM's Mon 23:45Z MNF props slot lands (it fired on 09-28:
newest pull 2026-09-28T23:45:08Z). Run at 23:30Z instead and the newest pull is Sunday 16:00Z (~31 h old).
Check the sheet's printed source age before trusting the run; if it is over 3 h, the 23:45Z pull has not landed.

## Scoring

### At 500 scored two-way legs (estimated: ~week 7-8)

```bash
# Score each week individually
for w in 3 4 5 6 7; do
  python3 nfl/pipeline/log_ai_opinions.py score --week $w \
    --out research/nfl_sim/fwd1_score_w${w}.md
done
```

The report filters by reader_model; cumulative P1/P2 is the sim's Brier and units
across all weeks at reader_model = nfl_sim_v1_156cd057.

### At 1,500 scored two-way legs (estimated: ~week 12-13)

Same commands with extended week range.

## Notes

- **Anchor rule (D210):** a game whose final anchored mean misses the market by > 1.0
  point on margin OR total is "unanchored"; its props are scored but reported separately.
- **Game lines (h2h, spreads, totals):** always no_view (the sim is market-anchored).
- **Pilot files:** never pooled; only included with `--include-pilot`.
- **Props slots (VM, WO12 deploy):** Tue 14:00 open; Wed-Sat 14:00 and Tue-Sat 02:00 mid; Thu 22:00 (TNF);
  Sun 15:00 and 16:00 close; Mon 23:45 (MNF). Corrected by Cowork (D222): the FWD1b runbook's pull times for
  TNF, London and MNF were wrong.
