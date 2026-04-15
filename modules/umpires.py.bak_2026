"""
Umpire module — static ratings table + live assignment lookup.

Umpire ratings are maintained as a "runs factor":
  1.00 = league neutral
  >1.00 = umpire historically associated with more scoring
  <1.00 = pitcher-friendly zone → fewer runs

Sources for updating: Baseball Reference umpire pages, Umpire Scorecards.
Update the UMPIRE_RATINGS dict as new data accumulates.

Last updated: 2025 season (2432 games via MLB Stats API, league avg 8.895 runs/game,
league std dev 4.593 runs/game).
Blend formula — existing umpires: 0.40 × 2025 + 0.60 × prior (capped ±0.050/yr).
New umpires (2025 debut): 0.25 × 2025 + 0.75 × 1.000 (conservative prior, ≥30 gm).
k_tendency unchanged for existing; set 0.000 for new (run data only — no K% available).

sigma_mult — used by simulation only (sim_projections.py):
  adjusted_sigma = base_sigma * ump_sigma_mult
  raw_sigma_mult = ump_std / league_std  (ddof=1, ≥30 games required)
  sigma_proxy    = 1 + 0.5 * (rf - 1.0)
  blended        = 0.5 * raw + 0.5 * proxy
  final          = clamp(blended, 0.95, 1.08)
  umpires with <30 games get sigma_mult = 1.00 (no adjustment).
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static umpire ratings — runs_factor relative to 1.00
# Based on career run-environment tendencies and K%/BB% zone analysis.
# 2020-2025 blended. Positive scores (>1.0) indicate run-friendly umpires.
# ---------------------------------------------------------------------------
UMPIRE_RATINGS: dict[str, dict] = {
    # Name (as returned by MLB Stats API) → {runs_factor, k_tendency, sigma_mult, note}
    # sigma_mult: simulation variance multiplier (adjusted_sigma = base_sigma × sigma_mult)
    # 1.00 = no variance adjustment; cap [0.95, 1.08]; <30 games → 1.00

    # Pitcher-friendly (tight zone → fewer runs)
    "Hunter Wendelstedt":  {"runs_factor": 0.960, "k_tendency": +0.025, "sigma_mult": 1.00,   "note": "Wide low zone"},
    "Dan Bellino":         {"runs_factor": 0.965, "k_tendency": +0.020, "sigma_mult": 1.00,   "note": "Pitcher-friendly"},
    "Nick Mahrley":        {"runs_factor": 0.971, "k_tendency": 0.000,  "sigma_mult": 0.95,   "note": "Pitcher-friendly (2025 debut, 31 gm)"},
    "Adam Hamari":         {"runs_factor": 0.973, "k_tendency": 0.000,  "sigma_mult": 1.00,   "note": "Pitcher-friendly (2025 debut, 31 gm)"},
    "Brennan Miller":      {"runs_factor": 0.973, "k_tendency": 0.000,  "sigma_mult": 0.95,   "note": "Pitcher-friendly (2025 debut, 31 gm)"},
    "Adam Beck":           {"runs_factor": 0.973, "k_tendency": 0.000,  "sigma_mult": 0.95,   "note": "Pitcher-friendly (2025 debut, 31 gm)"},
    "Will Little":         {"runs_factor": 0.974, "k_tendency": 0.000,  "sigma_mult": 0.95,   "note": "Pitcher-friendly (2025 debut, 31 gm)"},
    "Mark Ripperger":      {"runs_factor": 0.978, "k_tendency": 0.000,  "sigma_mult": 0.9882, "note": "Pitcher-friendly (2025 debut, 32 gm)"},
    "John Libka":          {"runs_factor": 0.978, "k_tendency": 0.000,  "sigma_mult": 1.0259, "note": "Pitcher-friendly (2025 debut, 31 gm)"},
    "Gabe Morales":        {"runs_factor": 0.984, "k_tendency": 0.000,  "sigma_mult": 0.9665, "note": "Pitcher-friendly (2025 debut, 32 gm)"},
    "Phil Cuzzi":          {"runs_factor": 0.920, "k_tendency": +0.015, "sigma_mult": 0.95,   "note": "Very pitcher-friendly; updated 2025 (capped)"},
    "Todd Tichenor":       {"runs_factor": 0.955, "k_tendency": +0.008, "sigma_mult": 0.95,   "note": "Pitcher-friendly; updated 2025"},
    "Nic Lentz":           {"runs_factor": 0.970, "k_tendency": -0.008, "sigma_mult": 1.027,  "note": "Shifted pitcher-friendly 2025; updated"},
    "Laz Diaz":            {"runs_factor": 0.996, "k_tendency": +0.018, "sigma_mult": 1.0359, "note": "Moved toward neutral 2025; updated"},
    "Ted Barrett":         {"runs_factor": 0.975, "k_tendency": +0.010, "sigma_mult": 1.00,   "note": "Slightly pitcher-friendly"},
    "Paul Nauert":         {"runs_factor": 0.980, "k_tendency": +0.010, "sigma_mult": 1.00,   "note": "Slightly tight"},
    "Tom Hallion":         {"runs_factor": 0.985, "k_tendency": +0.005, "sigma_mult": 1.00,   "note": "Near neutral"},
    "Brian Knight":        {"runs_factor": 0.985, "k_tendency": +0.005, "sigma_mult": 1.00,   "note": "Near neutral"},
    "Ron Kulpa":           {"runs_factor": 0.975, "k_tendency": +0.015, "sigma_mult": 1.00,   "note": "Pitcher-friendly"},
    "Fieldin Culbreth":    {"runs_factor": 0.978, "k_tendency": +0.012, "sigma_mult": 1.00,   "note": "Below avg run env"},
    "Marvin Hudson":       {"runs_factor": 0.985, "k_tendency": +0.005, "sigma_mult": 1.00,   "note": "Near neutral"},
    "Chris Segal":         {"runs_factor": 0.988, "k_tendency": +0.003, "sigma_mult": 1.00,   "note": "Near neutral"},
    "Greg Gibson":         {"runs_factor": 0.988, "k_tendency": +0.003, "sigma_mult": 1.00,   "note": "Near neutral"},

    # Neutral
    "Jim Reynolds":        {"runs_factor": 1.000, "k_tendency": 0.000,  "sigma_mult": 1.00,   "note": "League average"},
    "Mike Everitt":        {"runs_factor": 1.000, "k_tendency": 0.000,  "sigma_mult": 1.00,   "note": "League average"},
    "John Hirschbeck":     {"runs_factor": 1.000, "k_tendency": 0.000,  "sigma_mult": 1.00,   "note": "League average"},
    "Brian Gorman":        {"runs_factor": 1.000, "k_tendency": 0.000,  "sigma_mult": 1.00,   "note": "League average"},
    "Kerwin Danley":       {"runs_factor": 1.000, "k_tendency": 0.000,  "sigma_mult": 1.00,   "note": "League average"},
    "Roberto Ortiz":       {"runs_factor": 1.000, "k_tendency": 0.000,  "sigma_mult": 1.00,   "note": "League average"},
    "Quinn Wolcott":       {"runs_factor": 0.991, "k_tendency": 0.000,  "sigma_mult": 0.9517, "note": "Slightly pitcher-friendly; updated 2025"},
    "John Bacon":          {"runs_factor": 0.989, "k_tendency": -0.002, "sigma_mult": 0.95,   "note": "Near neutral; updated 2025"},
    "Edwin Moscoso":       {"runs_factor": 1.001, "k_tendency": -0.005, "sigma_mult": 1.0451, "note": "Near neutral; updated 2025"},
    "Mike Estabrook":      {"runs_factor": 0.979, "k_tendency": -0.010, "sigma_mult": 0.9594, "note": "Shifted pitcher-friendly 2025; updated"},
    "Lance Barksdale":     {"runs_factor": 1.013, "k_tendency": -0.007, "sigma_mult": 0.9513, "note": "Above avg run environment"},
    "Adrian Johnson":      {"runs_factor": 1.021, "k_tendency": -0.013, "sigma_mult": 0.9604, "note": "High run environments"},

    # Hitter-friendly (loose zone → more runs)
    "Clint Vondrak":       {"runs_factor": 1.053, "k_tendency": 0.000,  "sigma_mult": 1.08,   "note": "Very hitter-friendly (2025 debut, 30 gm)"},
    "Chris Conroy":        {"runs_factor": 1.055, "k_tendency": -0.002, "sigma_mult": 0.9625, "note": "Strongly hitter-friendly; updated 2025"},
    "Alfonso Marquez":     {"runs_factor": 1.032, "k_tendency": +0.008, "sigma_mult": 0.9558, "note": "Reversed to hitter-friendly 2025 (capped); updated"},
    "Bill Miller":         {"runs_factor": 1.034, "k_tendency": 0.000,  "sigma_mult": 1.0676, "note": "More hitter-friendly 2025; updated"},
    "Alan Porter":         {"runs_factor": 1.031, "k_tendency": 0.000,  "sigma_mult": 1.08,   "note": "Hitter-friendly (2025 debut, 30 gm)"},
    "Doug Eddings":        {"runs_factor": 1.028, "k_tendency": 0.000,  "sigma_mult": 1.08,   "note": "Hitter-friendly (2025 debut, 33 gm)"},
    "Malachi Moore":       {"runs_factor": 1.025, "k_tendency": 0.000,  "sigma_mult": 1.001,  "note": "Hitter-friendly (2025 debut, 30 gm)"},
    "Alex Tosi":           {"runs_factor": 1.024, "k_tendency": -0.004, "sigma_mult": 0.9908, "note": "More hitter-friendly; updated 2025"},
    "CB Bucknor":          {"runs_factor": 1.035, "k_tendency": -0.020, "sigma_mult": 1.00,   "note": "Inconsistent zone, more walks"},
    "Angel Hernandez":     {"runs_factor": 1.025, "k_tendency": -0.015, "sigma_mult": 1.00,   "note": "Inconsistent — tends high scoring"},
    "Gerry Davis":         {"runs_factor": 1.020, "k_tendency": -0.012, "sigma_mult": 1.00,   "note": "Hitter-friendly later career"},
    "Ben May":             {"runs_factor": 1.024, "k_tendency": 0.000,  "sigma_mult": 1.0393, "note": "Hitter-friendly (2025 debut, 30 gm)"},
    "David Rackley":       {"runs_factor": 1.021, "k_tendency": 0.000,  "sigma_mult": 1.0099, "note": "Hitter-friendly (2025 debut, 30 gm)"},
    "Brian Walsh":         {"runs_factor": 1.020, "k_tendency": 0.000,  "sigma_mult": 1.0689, "note": "Hitter-friendly (2025 debut, 32 gm)"},
    "Joe West":            {"runs_factor": 1.015, "k_tendency": -0.008, "sigma_mult": 1.00,   "note": "Career-wide slight hitter lean"},
    "Bill Welke":          {"runs_factor": 1.018, "k_tendency": -0.010, "sigma_mult": 1.00,   "note": "High run environments"},
    "Tim Welke":           {"runs_factor": 1.015, "k_tendency": -0.008, "sigma_mult": 1.00,   "note": "Hitter-friendly"},
    "Jim Joyce":           {"runs_factor": 1.012, "k_tendency": -0.006, "sigma_mult": 1.00,   "note": "Slightly hitter-friendly"},
    "Dana DeMuth":         {"runs_factor": 1.010, "k_tendency": -0.005, "sigma_mult": 1.00,   "note": "Slightly hitter-friendly"},
    "Jerry Layne":         {"runs_factor": 1.010, "k_tendency": -0.005, "sigma_mult": 1.00,   "note": "Near neutral, slight lean"},
    "Jim Wolf":            {"runs_factor": 1.016, "k_tendency": 0.000,  "sigma_mult": 0.95,   "note": "Hitter-friendly (2025 debut, 30 gm)"},
    "Ramon De Jesus":      {"runs_factor": 1.014, "k_tendency": 0.000,  "sigma_mult": 1.0403, "note": "Hitter-friendly (2025 debut, 31 gm)"},
    "Vic Carapazza":       {"runs_factor": 1.018, "k_tendency": 0.000,  "sigma_mult": 1.0566, "note": "More hitter-friendly; updated 2025"},
    "Tripp Gibson":        {"runs_factor": 1.008, "k_tendency": -0.004, "sigma_mult": 1.00,   "note": "Near neutral"},
    "Pat Hoberg":          {"runs_factor": 1.005, "k_tendency": -0.002, "sigma_mult": 1.00,   "note": "Near neutral"},
    "Ryan Blakney":        {"runs_factor": 1.005, "k_tendency": -0.002, "sigma_mult": 1.00,   "note": "Near neutral"},
    "Jeremie Rehak":       {"runs_factor": 1.008, "k_tendency": -0.004, "sigma_mult": 1.00,   "note": "Near neutral"},
}

NEUTRAL_RATING = {"runs_factor": 1.000, "k_tendency": 0.000, "sigma_mult": 1.00, "note": "Unknown umpire"}


def get_umpire_rating(umpire_name: str | None) -> dict:
    """
    Return the runs_factor for *umpire_name*.
    Falls back to neutral (1.000) if the umpire is unknown.
    """
    if not umpire_name:
        return {**NEUTRAL_RATING, "name": "Unknown"}

    # Exact match
    if umpire_name in UMPIRE_RATINGS:
        return {**UMPIRE_RATINGS[umpire_name], "name": umpire_name}

    # Last-name match
    last = umpire_name.split()[-1].lower()
    for name, rating in UMPIRE_RATINGS.items():
        if name.split()[-1].lower() == last:
            logger.debug(f"Umpire partial match: '{umpire_name}' → '{name}'")
            return {**rating, "name": name}

    logger.debug(f"Unknown umpire: {umpire_name} — using neutral rating")
    return {**NEUTRAL_RATING, "name": umpire_name}


def list_all_umpires() -> list[dict]:
    """Return all umpires sorted by runs_factor (most pitcher-friendly first)."""
    return sorted(
        [{"name": k, **v} for k, v in UMPIRE_RATINGS.items()],
        key=lambda x: x["runs_factor"]
    )
