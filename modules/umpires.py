"""
Umpire module — static ratings table + live assignment lookup.

Umpire ratings are maintained as a "runs factor":
  1.00 = league neutral
  >1.00 = umpire historically associated with more scoring
  <1.00 = pitcher-friendly zone → fewer runs

Sources for updating: Baseball Reference umpire pages, Umpire Scorecards.
Update the UMPIRE_RATINGS dict as new data accumulates.
"""

import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static umpire ratings — runs_factor relative to 1.00
# Based on career K%, BB%, and run-environment tendencies (2020-2024)
# Positive scores (>1.0) indicate run-friendly umpires
# ---------------------------------------------------------------------------
UMPIRE_RATINGS: dict[str, dict] = {
    # Name (as returned by MLB Stats API) → {runs_factor, k_tendency, note}

    # Pitcher-friendly (tight zone → fewer runs)
    "Hunter Wendelstedt":  {"runs_factor": 0.960, "k_tendency": +0.025, "note": "Wide low zone"},
    "Dan Bellino":         {"runs_factor": 0.965, "k_tendency": +0.020, "note": "Pitcher-friendly"},
    "Phil Cuzzi":          {"runs_factor": 0.970, "k_tendency": +0.015, "note": "Consistent, low scoring"},
    "Laz Diaz":            {"runs_factor": 0.975, "k_tendency": +0.018, "note": "Large zone"},
    "Ted Barrett":         {"runs_factor": 0.975, "k_tendency": +0.010, "note": "Slightly pitcher-friendly"},
    "Paul Nauert":         {"runs_factor": 0.980, "k_tendency": +0.010, "note": "Slightly tight"},
    "Alfonso Marquez":     {"runs_factor": 0.982, "k_tendency": +0.008, "note": "Slightly tight zone"},
    "Tom Hallion":         {"runs_factor": 0.985, "k_tendency": +0.005, "note": "Near neutral"},
    "Brian Knight":        {"runs_factor": 0.985, "k_tendency": +0.005, "note": "Near neutral"},
    "Ron Kulpa":           {"runs_factor": 0.975, "k_tendency": +0.015, "note": "Pitcher-friendly"},
    "Fieldin Culbreth":    {"runs_factor": 0.978, "k_tendency": +0.012, "note": "Below avg run env"},
    "Todd Tichenor":       {"runs_factor": 0.982, "k_tendency": +0.008, "note": "Slightly pitcher-friendly"},
    "Marvin Hudson":       {"runs_factor": 0.985, "k_tendency": +0.005, "note": "Near neutral"},
    "Chris Segal":         {"runs_factor": 0.988, "k_tendency": +0.003, "note": "Near neutral"},
    "Greg Gibson":         {"runs_factor": 0.988, "k_tendency": +0.003, "note": "Near neutral"},

    # Neutral
    "Bill Miller":         {"runs_factor": 1.000, "k_tendency": 0.000, "note": "League average"},
    "Jim Reynolds":        {"runs_factor": 1.000, "k_tendency": 0.000, "note": "League average"},
    "Mike Everitt":        {"runs_factor": 1.000, "k_tendency": 0.000, "note": "League average"},
    "John Hirschbeck":     {"runs_factor": 1.000, "k_tendency": 0.000, "note": "League average"},
    "Brian Gorman":        {"runs_factor": 1.000, "k_tendency": 0.000, "note": "League average"},
    "Kerwin Danley":       {"runs_factor": 1.000, "k_tendency": 0.000, "note": "League average"},
    "Quinn Wolcott":       {"runs_factor": 1.000, "k_tendency": 0.000, "note": "League average"},
    "Roberto Ortiz":       {"runs_factor": 1.000, "k_tendency": 0.000, "note": "League average"},
    "Vic Carapazza":       {"runs_factor": 1.000, "k_tendency": 0.000, "note": "League average"},

    # Hitter-friendly (loose zone → more runs)
    "CB Bucknor":          {"runs_factor": 1.035, "k_tendency": -0.020, "note": "Inconsistent zone, more walks"},
    "Angel Hernandez":     {"runs_factor": 1.025, "k_tendency": -0.015, "note": "Inconsistent — tends high scoring"},
    "Gerry Davis":         {"runs_factor": 1.020, "k_tendency": -0.012, "note": "Hitter-friendly later career"},
    "Joe West":            {"runs_factor": 1.015, "k_tendency": -0.008, "note": "Career-wide slight hitter lean"},
    "Bill Welke":          {"runs_factor": 1.018, "k_tendency": -0.010, "note": "High run environments"},
    "Tim Welke":           {"runs_factor": 1.015, "k_tendency": -0.008, "note": "Hitter-friendly"},
    "Jim Joyce":           {"runs_factor": 1.012, "k_tendency": -0.006, "note": "Slightly hitter-friendly"},
    "Dana DeMuth":         {"runs_factor": 1.010, "k_tendency": -0.005, "note": "Slightly hitter-friendly"},
    "Jerry Layne":         {"runs_factor": 1.010, "k_tendency": -0.005, "note": "Near neutral, slight lean"},
    "Lance Barksdale":     {"runs_factor": 1.012, "k_tendency": -0.007, "note": "Above avg run environment"},
    "Adrian Johnson":      {"runs_factor": 1.022, "k_tendency": -0.013, "note": "High run environments"},
    "Nic Lentz":           {"runs_factor": 1.015, "k_tendency": -0.008, "note": "Hitter-friendly zone"},
    "Mike Estabrook":      {"runs_factor": 1.020, "k_tendency": -0.010, "note": "Above avg run environment"},
    "Tripp Gibson":        {"runs_factor": 1.008, "k_tendency": -0.004, "note": "Near neutral"},
    "Pat Hoberg":          {"runs_factor": 1.005, "k_tendency": -0.002, "note": "Near neutral"},
    "Ryan Blakney":        {"runs_factor": 1.005, "k_tendency": -0.002, "note": "Near neutral"},
    "Alex Tosi":           {"runs_factor": 1.008, "k_tendency": -0.004, "note": "Slight hitter lean"},
    "John Bacon":          {"runs_factor": 1.005, "k_tendency": -0.002, "note": "Near neutral"},
    "Edwin Moscoso":       {"runs_factor": 1.010, "k_tendency": -0.005, "note": "Hitter-friendly"},
    "Jeremie Rehak":       {"runs_factor": 1.008, "k_tendency": -0.004, "note": "Near neutral"},
    "Chris Conroy":        {"runs_factor": 1.005, "k_tendency": -0.002, "note": "Near neutral"},
}

NEUTRAL_RATING = {"runs_factor": 1.000, "k_tendency": 0.000, "note": "Unknown umpire"}


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
