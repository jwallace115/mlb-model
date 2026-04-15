"""
Umpire module -- static ratings table + live assignment lookup.

Umpire ratings are maintained as a "runs factor":
  1.00 = league neutral
  >1.00 = umpire historically associated with more scoring
  <1.00 = pitcher-friendly zone -> fewer runs

FROZEN 2026 REBUILD -- derived from game_table.parquet (2022-2025 completed games).
Methodology:
  - Completed 2022-2025 games only (9,715 games, league_avg = 8.870 runs/game)
  - Minimum 30 games required for non-neutral rating
  - runs_factor = ump_avg_total / league_avg_total
  - Clamped to [0.900, 1.100] (10 umpires hit bounds)
  - k_tendency = 0.000 (not rebuildable from game_table -- set neutral)
  - sigma_mult = 1.00 (default; not rebuildable from game_table alone)
  - 19 umpires with <30 games assigned neutral (1.000 / 0.000 / 1.00)
  - Normalization: NFKD unicode decomposition strips combining marks;
    lookup tries normalized match to handle accented names (e.g. Alfonso Marquez)

Coverage: 92/111 GT umpires rated (82.9%), 9,626/9,902 games covered (97.2%).
"""

import logging
import unicodedata

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Static umpire ratings -- runs_factor relative to 1.00
# Derived from game_table.parquet 2022-2025 completed games (9,715 total).
# league_avg_total = 8.870 runs/game.
# Sorted by runs_factor ascending (pitcher-friendly first).
# ---------------------------------------------------------------------------
UMPIRE_RATINGS: dict[str, dict] = {
    # Name (as returned by MLB Stats API) -> {runs_factor, k_tendency, sigma_mult, ...}

    # -- Pitcher-friendly (clamped to 0.900 floor) --------------------------
    "Austin Jones":        {"runs_factor": 0.9000, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 36,  "note": "Frozen 2026: avg=7.583/gm, 36gm 2022-2025 [raw=0.8549 CLAMPED]"},
    "Brennan Miller":      {"runs_factor": 0.9000, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 104, "note": "Frozen 2026: avg=7.731/gm, 104gm 2022-2025 [raw=0.8715 CLAMPED]"},
    "Cory Blaser":         {"runs_factor": 0.9000, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 112, "note": "Frozen 2026: avg=7.875/gm, 112gm 2022-2025 [raw=0.8878 CLAMPED]"},
    "Alex MacKay":         {"runs_factor": 0.9000, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 82,  "note": "Frozen 2026: avg=7.902/gm, 82gm 2022-2025 [raw=0.8909 CLAMPED]"},
    "Phil Cuzzi":          {"runs_factor": 0.9000, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 121, "note": "Frozen 2026: avg=7.967/gm, 121gm 2022-2025 [raw=0.8982 CLAMPED]"},
    "John Bacon":          {"runs_factor": 0.9000, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 75,  "note": "Frozen 2026: avg=7.973/gm, 75gm 2022-2025 [raw=0.8989 CLAMPED]"},
    "Jacob Metz":          {"runs_factor": 0.9000, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 42,  "note": "Frozen 2026: avg=7.976/gm, 42gm 2022-2025 [raw=0.8992 CLAMPED]"},
    # -- Pitcher-friendly ---------------------------------------------------
    "Ryan Blakney":        {"runs_factor": 0.9162, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 118, "note": "Frozen 2026: avg=8.127/gm, 118gm 2022-2025"},
    "Ron Kulpa":           {"runs_factor": 0.9268, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 68,  "note": "Frozen 2026: avg=8.221/gm, 68gm 2022-2025"},
    "Dan Merzel":          {"runs_factor": 0.9289, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 121, "note": "Frozen 2026: avg=8.240/gm, 121gm 2022-2025"},
    "Chris Conroy":        {"runs_factor": 0.9354, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 84,  "note": "Frozen 2026: avg=8.298/gm, 84gm 2022-2025"},
    "David Rackley":       {"runs_factor": 0.9398, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 122, "note": "Frozen 2026: avg=8.336/gm, 122gm 2022-2025"},
    "Tony Randazzo":       {"runs_factor": 0.9400, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 77,  "note": "Frozen 2026: avg=8.338/gm, 77gm 2022-2025"},
    "Jeremy Riggs":        {"runs_factor": 0.9470, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 70,  "note": "Frozen 2026: avg=8.400/gm, 70gm 2022-2025"},
    "CB Bucknor":          {"runs_factor": 0.9478, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 113, "note": "Frozen 2026: avg=8.407/gm, 113gm 2022-2025"},
    "Nic Lentz":           {"runs_factor": 0.9485, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 121, "note": "Frozen 2026: avg=8.413/gm, 121gm 2022-2025"},
    "Roberto Ortiz":       {"runs_factor": 0.9515, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 116, "note": "Frozen 2026: avg=8.440/gm, 116gm 2022-2025"},
    "Nestor Ceja":         {"runs_factor": 0.9555, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 122, "note": "Frozen 2026: avg=8.475/gm, 122gm 2022-2025"},
    "Doug Eddings":        {"runs_factor": 0.9555, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 124, "note": "Frozen 2026: avg=8.476/gm, 124gm 2022-2025"},
    "Brian Knight":        {"runs_factor": 0.9567, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 72,  "note": "Frozen 2026: avg=8.486/gm, 72gm 2022-2025"},
    "Adam Beck":           {"runs_factor": 0.9610, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 122, "note": "Frozen 2026: avg=8.525/gm, 122gm 2022-2025"},
    "Bill Miller":         {"runs_factor": 0.9614, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 127, "note": "Frozen 2026: avg=8.528/gm, 127gm 2022-2025"},
    "Paul Clemons":        {"runs_factor": 0.9615, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 70,  "note": "Frozen 2026: avg=8.529/gm, 70gm 2022-2025"},
    "Larry Vanover":       {"runs_factor": 0.9625, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 67,  "note": "Frozen 2026: avg=8.537/gm, 67gm 2022-2025"},
    "Rob Drake":           {"runs_factor": 0.9631, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 81,  "note": "Frozen 2026: avg=8.543/gm, 81gm 2022-2025"},
    "Adam Hamari":         {"runs_factor": 0.9650, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 125, "note": "Frozen 2026: avg=8.560/gm, 125gm 2022-2025"},
    "Edwin Jimenez":       {"runs_factor": 0.9651, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 66,  "note": "Frozen 2026: avg=8.561/gm, 66gm 2022-2025"},
    "Manny Gonzalez":      {"runs_factor": 0.9714, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 112, "note": "Frozen 2026: avg=8.616/gm, 112gm 2022-2025"},
    "Emil Jimenez":        {"runs_factor": 0.9745, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 90,  "note": "Frozen 2026: avg=8.644/gm, 90gm 2022-2025"},
    "D.J. Reyburn":        {"runs_factor": 0.9755, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 118, "note": "Frozen 2026: avg=8.653/gm, 118gm 2022-2025"},
    "Charlie Ramos":       {"runs_factor": 0.9787, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 113, "note": "Frozen 2026: avg=8.681/gm, 113gm 2022-2025"},
    "Will Little":         {"runs_factor": 0.9830, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 107, "note": "Frozen 2026: avg=8.720/gm, 107gm 2022-2025"},
    "Junior Valentine":    {"runs_factor": 0.9834, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 119, "note": "Frozen 2026: avg=8.723/gm, 119gm 2022-2025"},
    "Stu Scheurwater":     {"runs_factor": 0.9841, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 118, "note": "Frozen 2026: avg=8.729/gm, 118gm 2022-2025"},
    "Bruce Dreckman":      {"runs_factor": 0.9854, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 108, "note": "Frozen 2026: avg=8.741/gm, 108gm 2022-2025"},
    "Chris Segal":         {"runs_factor": 0.9888, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 122, "note": "Frozen 2026: avg=8.770/gm, 122gm 2022-2025"},
    "Laz Diaz":            {"runs_factor": 0.9897, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 113, "note": "Frozen 2026: avg=8.779/gm, 113gm 2022-2025"},
    "Brian O'Nora":        {"runs_factor": 0.9904, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 107, "note": "Frozen 2026: avg=8.785/gm, 107gm 2022-2025"},
    "Alex Tosi":           {"runs_factor": 0.9909, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 114, "note": "Frozen 2026: avg=8.789/gm, 114gm 2022-2025"},
    "Shane Livensparger":  {"runs_factor": 0.9916, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 103, "note": "Frozen 2026: avg=8.796/gm, 103gm 2022-2025"},
    "Quinn Wolcott":       {"runs_factor": 0.9917, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 113, "note": "Frozen 2026: avg=8.796/gm, 113gm 2022-2025"},
    # -- Near-neutral -------------------------------------------------------
    "Jim Wolf":            {"runs_factor": 0.9977, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 100, "note": "Frozen 2026: avg=8.850/gm, 100gm 2022-2025"},
    "Todd Tichenor":       {"runs_factor": 0.9978, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 114, "note": "Frozen 2026: avg=8.851/gm, 114gm 2022-2025"},
    "Lance Barksdale":     {"runs_factor": 0.9987, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 120, "note": "Frozen 2026: avg=8.858/gm, 120gm 2022-2025"},
    "Mark Carlson":        {"runs_factor": 0.9987, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 92,  "note": "Frozen 2026: avg=8.859/gm, 92gm 2022-2025"},
    "Nick Mahrley":        {"runs_factor": 0.9989, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 122, "note": "Frozen 2026: avg=8.861/gm, 122gm 2022-2025"},
    "Erich Bacchus":       {"runs_factor": 0.9989, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 115, "note": "Frozen 2026: avg=8.861/gm, 115gm 2022-2025"},
    "Paul Emmel":          {"runs_factor": 0.9998, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 38,  "note": "Frozen 2026: avg=8.868/gm, 38gm 2022-2025"},
    "Mike Estabrook":      {"runs_factor": 1.0012, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 101, "note": "Frozen 2026: avg=8.881/gm, 101gm 2022-2025"},
    "Chad Fairchild":      {"runs_factor": 1.0018, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 114, "note": "Frozen 2026: avg=8.886/gm, 114gm 2022-2025"},
    "John Tumpane":        {"runs_factor": 1.0049, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 116, "note": "Frozen 2026: avg=8.914/gm, 116gm 2022-2025"},
    "Jeremie Rehak":       {"runs_factor": 1.0054, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 110, "note": "Frozen 2026: avg=8.918/gm, 110gm 2022-2025"},
    "Vic Carapazza":       {"runs_factor": 1.0058, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 127, "note": "Frozen 2026: avg=8.921/gm, 127gm 2022-2025"},
    "Hunter Wendelstedt":  {"runs_factor": 1.0059, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 90,  "note": "Frozen 2026: avg=8.922/gm, 90gm 2022-2025"},
    "Marvin Hudson":       {"runs_factor": 1.0085, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 111, "note": "Frozen 2026: avg=8.946/gm, 111gm 2022-2025"},
    "James Hoye":          {"runs_factor": 1.0099, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 120, "note": "Frozen 2026: avg=8.958/gm, 120gm 2022-2025"},
    "Jansen Visconti":     {"runs_factor": 1.0118, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 120, "note": "Frozen 2026: avg=8.975/gm, 120gm 2022-2025"},
    # -- Hitter-friendly ----------------------------------------------------
    "Sean Barber":         {"runs_factor": 1.0156, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 119, "note": "Frozen 2026: avg=9.008/gm, 119gm 2022-2025"},
    "Mark Ripperger":      {"runs_factor": 1.0193, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 122, "note": "Frozen 2026: avg=9.041/gm, 122gm 2022-2025"},
    "Lance Barrett":       {"runs_factor": 1.0193, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 122, "note": "Frozen 2026: avg=9.041/gm, 122gm 2022-2025"},
    "Carlos Torres":       {"runs_factor": 1.0202, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 121, "note": "Frozen 2026: avg=9.050/gm, 121gm 2022-2025"},
    "Ryan Wills":          {"runs_factor": 1.0229, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 123, "note": "Frozen 2026: avg=9.073/gm, 123gm 2022-2025"},
    "Malachi Moore":       {"runs_factor": 1.0246, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 113, "note": "Frozen 2026: avg=9.088/gm, 113gm 2022-2025"},
    "Gabe Morales":        {"runs_factor": 1.0266, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 122, "note": "Frozen 2026: avg=9.107/gm, 122gm 2022-2025"},
    "Tripp Gibson":        {"runs_factor": 1.0293, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 115, "note": "Frozen 2026: avg=9.130/gm, 115gm 2022-2025"},
    "Chad Whitson":        {"runs_factor": 1.0314, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 101, "note": "Frozen 2026: avg=9.149/gm, 101gm 2022-2025"},
    "Dan Iassogna":        {"runs_factor": 1.0325, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 120, "note": "Frozen 2026: avg=9.158/gm, 120gm 2022-2025"},
    "John Libka":          {"runs_factor": 1.0346, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 124, "note": "Frozen 2026: avg=9.177/gm, 124gm 2022-2025"},
    "Scott Barry":         {"runs_factor": 1.0359, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 85,  "note": "Frozen 2026: avg=9.188/gm, 85gm 2022-2025"},
    "Ben May":             {"runs_factor": 1.0416, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 117, "note": "Frozen 2026: avg=9.239/gm, 117gm 2022-2025"},
    "Pat Hoberg":          {"runs_factor": 1.0418, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 58,  "note": "Frozen 2026: avg=9.241/gm, 58gm 2022-2025"},
    "Nate Tomlinson":      {"runs_factor": 1.0465, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 106, "note": "Frozen 2026: avg=9.283/gm, 106gm 2022-2025"},
    "Derek Thomas":        {"runs_factor": 1.0475, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 72,  "note": "Frozen 2026: avg=9.292/gm, 72gm 2022-2025"},
    "Ryan Additon":        {"runs_factor": 1.0509, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 115, "note": "Frozen 2026: avg=9.322/gm, 115gm 2022-2025"},
    "Tom Hanahan":         {"runs_factor": 1.0522, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 72,  "note": "Frozen 2026: avg=9.333/gm, 72gm 2022-2025"},
    "Ramon De Jesus":      {"runs_factor": 1.0532, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 120, "note": "Frozen 2026: avg=9.342/gm, 120gm 2022-2025"},
    "Brock Ballou":        {"runs_factor": 1.0535, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 58,  "note": "Frozen 2026: avg=9.345/gm, 58gm 2022-2025"},
    "Brian Walsh":         {"runs_factor": 1.0546, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 79,  "note": "Frozen 2026: avg=9.354/gm, 79gm 2022-2025"},
    "Alan Porter":         {"runs_factor": 1.0554, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 119, "note": "Frozen 2026: avg=9.361/gm, 119gm 2022-2025"},
    "Edwin Moscoso":       {"runs_factor": 1.0554, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 130, "note": "Frozen 2026: avg=9.362/gm, 130gm 2022-2025"},
    "Jordan Baker":        {"runs_factor": 1.0605, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 118, "note": "Frozen 2026: avg=9.407/gm, 118gm 2022-2025"},
    "Angel Hernandez":     {"runs_factor": 1.0640, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 48,  "note": "Frozen 2026: avg=9.438/gm, 48gm 2022-2025"},
    "Jerry Layne":         {"runs_factor": 1.0675, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 32,  "note": "Frozen 2026: avg=9.469/gm, 32gm 2022-2025"},
    # Canonical accented name; normalization also matches ASCII "Alfonso Marquez"
    "Alfonso M\u00e1rquez": {"runs_factor": 1.0700, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 118, "note": "Frozen 2026: avg=9.492/gm, 118gm 2022-2025"},
    "Chris Guccione":      {"runs_factor": 1.0788, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 109, "note": "Frozen 2026: avg=9.569/gm, 109gm 2022-2025"},
    "Mike Muchlinski":     {"runs_factor": 1.0788, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 116, "note": "Frozen 2026: avg=9.569/gm, 116gm 2022-2025"},
    "Adrian Johnson":      {"runs_factor": 1.0789, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 121, "note": "Frozen 2026: avg=9.570/gm, 121gm 2022-2025"},
    "Clint Vondrak":       {"runs_factor": 1.0812, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 122, "note": "Frozen 2026: avg=9.590/gm, 122gm 2022-2025"},
    "Andy Fletcher":       {"runs_factor": 1.0892, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 121, "note": "Frozen 2026: avg=9.661/gm, 121gm 2022-2025"},
    # -- Hitter-friendly (clamped to 1.100 ceiling) -------------------------
    "Dan Bellino":         {"runs_factor": 1.1000, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 124, "note": "Frozen 2026: avg=9.806/gm, 124gm 2022-2025 [raw=1.1056 CLAMPED]"},
    "Jeff Nelson":         {"runs_factor": 1.1000, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 56,  "note": "Frozen 2026: avg=9.893/gm, 56gm 2022-2025 [raw=1.1153 CLAMPED]"},
    "Mark Wegner":         {"runs_factor": 1.1000, "k_tendency": 0.000, "sigma_mult": 1.00, "games_2022_2025": 100, "note": "Frozen 2026: avg=9.940/gm, 100gm 2022-2025 [raw=1.1206 CLAMPED]"},
}

NEUTRAL_RATING = {"runs_factor": 1.000, "k_tendency": 0.000, "sigma_mult": 1.00, "note": "Neutral -- <30 games or unknown"}


def _normalize_name(name: str) -> str:
    """NFKD normalization strips combining accents for deterministic matching."""
    normalized = unicodedata.normalize('NFKD', str(name))
    normalized = ''.join(c for c in normalized if not unicodedata.combining(c))
    return ' '.join(normalized.split()).strip()


# Build normalized-name lookup at import time (accented keys map to their record)
_NORM_LOOKUP: dict[str, str] = {
    _normalize_name(k): k for k in UMPIRE_RATINGS
}


def get_umpire_rating(umpire_name: str | None) -> dict:
    """
    Return the rating dict for *umpire_name*.

    Lookup order:
      1. Exact match against UMPIRE_RATINGS keys
      2. Normalized (NFKD accent-stripped) match via _NORM_LOOKUP
      3. Neutral fallback (1.000 / 0.000 / 1.00)

    The last-name-only fallback has been removed -- it caused cross-family
    collisions (e.g. Lance Barrett incorrectly matched Ted Barrett).
    """
    if not umpire_name:
        return {**NEUTRAL_RATING, "name": "Unknown"}

    # Exact match
    if umpire_name in UMPIRE_RATINGS:
        return {**UMPIRE_RATINGS[umpire_name], "name": umpire_name}

    # Normalized match (handles accented names like Alfonso Marquez / Alfonso Marquez)
    norm = _normalize_name(umpire_name)
    if norm in _NORM_LOOKUP:
        canonical = _NORM_LOOKUP[norm]
        logger.debug(f"Umpire normalized match: '{umpire_name}' -> '{canonical}'")
        return {**UMPIRE_RATINGS[canonical], "name": canonical}

    logger.debug(f"Unknown umpire: '{umpire_name}' -- using neutral rating")
    return {**NEUTRAL_RATING, "name": umpire_name}


def list_all_umpires() -> list[dict]:
    """Return all umpires sorted by runs_factor (most pitcher-friendly first)."""
    return sorted(
        [{"name": k, **v} for k, v in UMPIRE_RATINGS.items()],
        key=lambda x: x["runs_factor"]
    )
