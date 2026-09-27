"""NFL week 4 (2026-09-27) full-slate reader fill — reader_method_v1, claude-opus-5-5.
Game views are the reader's own reads of the layers (Hard Rock vs Pinnacle price, line movement since the
Sunday-night open, QB situations from the props board / news). Props follow the game view (total lean, QB script).
"""
import sys, numpy as np, pandas as pd
S = sys.argv[1]
s = pd.read_csv(f"{S}/wk4_sheet.csv")

# home team -> (sp_adj to HOME-cover prob, tot_adj to OVER prob, conf_side, conf_tot, tag_side, tag_tot, reason_side, reason_tot)
V = {
 "Buffalo Bills": (+0.035, 0.0, 72, 12, "price_vs_sharp", "matchup",
   "BUF -7 at HR vs -7.5 at Pinnacle: the key number 7 for free; Allen at home vs a Chargers team that travels east early.",
   "50 is the same at HR and Pinnacle; no total read, slight under on a big early road trip for LAC."),
 "Washington Commanders": (-0.045, -0.015, 75, 30, "price_vs_sharp", "injury_news",
   "SEA -8.5 at HR vs -9.5 at Pinnacle after Daniels (elbow) out; Mariota starts. HR is a full point stale.",
   "Mariota for Daniels and a 40.5 total: Washington's offense shrinks; lean under."),
 "New York Giants": (+0.03, +0.03, 62, 55, "price_vs_sharp", "price_vs_sharp",
   "NYG -2 at HR vs -2.5 Pinnacle; Winston replaces Dart and pushes the ball against a Titans rookie QB.",
   "38 at HR vs 38.5 Pinnacle; Winston's volume and turnovers create short fields both ways. Over."),
 "Pittsburgh Steelers": (+0.035, +0.02, 64, 40, "price_vs_sharp", "price_vs_sharp",
   "PIT +3 at even money vs -120 on the other side: paying for the 3 is free here; Rodgers at home as a dog.",
   "42.5 at HR vs 43 at Pinnacle; Burrow-Rodgers can move the ball. Over the half point."),
 "Cleveland Browns": (+0.03, +0.01, 58, 20, "line_move", "line_move",
   "Moved 3 to 1.5 toward CLE at Pinnacle; HR still +2. Take CLE +2 with the move and the extra half point.",
   "Total rose 41 to 42 at Pinnacle; small over lean with the move."),
 "San Francisco 49ers": (-0.03, -0.02, 55, 38, "line_move", "price_vs_sharp",
   "Opened -8.5, now -7.5 at Pinnacle: money on ARI. ARI +7.5 with the move; Brissett keeps it close enough.",
   "48 at HR vs 47.5 Pinnacle: under the extra half point."),
 "Jacksonville Jaguars": (-0.025, +0.015, 45, 25, "matchup", "line_move",
   "JAX -3 priced -105 and NE +3 -115: the market leans NE at the key number; Maye's form over Lawrence. NE +3.",
   "Total ticked 45 to 45.5 at Pinnacle; slight over with the move."),
 "Miami Dolphins": (-0.02, -0.02, 40, 36, "price_vs_sharp", "matchup",
   "KC -9.5 at HR vs -10 at Pinnacle: half a point better than the sharp number, with Willis starting for Miami.",
   "Willis-led Miami offence is limited and KC grinds with a lead; under 45.5."),
 "Detroit Lions": (+0.015, +0.015, 30, 28, "matchup", "line_move",
   "DET -7 at home against Geno Smith's Jets; Lions' offence at home clears a touchdown margin a bit more often.",
   "Total 48 to 48.5 at Pinnacle; Detroit home games run high. Small over."),
 "Indianapolis Colts": (+0.015, -0.015, 26, 28, "matchup", "matchup",
   "IND +1.5 at home in a division game; the hook matters little but home dog side slightly preferred.",
   "Division game, two defences that limit big plays; under 42.5."),
 "Tampa Bay Buccaneers": (+0.015, +0.02, 28, 34, "matchup", "price_vs_sharp",
   "TB +1 at home is basically a pick; Mayfield at home vs Murray's Vikings, lean home.",
   "42.5 at HR vs 43 Pinnacle: over the half point."),
 "New Orleans Saints": (-0.02, +0.01, 32, 18, "matchup", "price_vs_sharp",
   "LV +3.5 gets the hook past 3 against a rookie QB favourite; take the points.",
   "43.5 at HR vs 44 Pinnacle, but the over is -115; small over."),
 "Dallas Cowboys": (-0.025, -0.02, 48, 32, "price_vs_sharp", "price_vs_sharp",
   "BAL -3 at HR vs -3.5 at Pinnacle: the hook off the key number for -120; Lamar vs a Dallas defence that leaks.",
   "53.5 at HR vs 53 Pinnacle: under the extra half point despite the upward move."),
 "Denver Broncos": (+0.02, -0.015, 34, 26, "matchup", "matchup",
   "DEN +1.5 at altitude against a Rams team on the road; home dog with the hook.",
   "Two good defences, Nix limited downfield: under 44."),
 "Chicago Bears": (+0.02, -0.01, 30, 20, "matchup", "matchup",
   "CHI +3.5 at home on Monday: the hook past 3 against a road favourite; take the points.",
   "Monday night, cold-ish Chicago, two defences: slight under 42."),
}
# QB team and script: +1 = expected to trail (more passing), -1 = expected to lead
QB = {"Malik Willis": ("Miami Dolphins", +1), "Patrick Mahomes": ("Miami Dolphins", -1),
      "Geno Smith": ("Detroit Lions", +1), "Jared Goff": ("Detroit Lions", -1),
      "C.J. Stroud": ("Indianapolis Colts", 0), "Daniel Jones": ("Indianapolis Colts", 0),
      "Drake Maye": ("Jacksonville Jaguars", 0), "Trevor Lawrence": ("Jacksonville Jaguars", 0),
      "Marcus Mariota": ("Washington Commanders", +1), "Sam Darnold": ("Washington Commanders", -1),
      "Cam Ward": ("New York Giants", +1), "Jameis Winston": ("New York Giants", -1),
      "Bryce Young": ("Cleveland Browns", 0), "Deshaun Watson": ("Cleveland Browns", 0),
      "Aaron Rodgers": ("Pittsburgh Steelers", 0), "Joe Burrow": ("Pittsburgh Steelers", 0),
      "Josh Allen": ("Buffalo Bills", -1), "Justin Herbert": ("Buffalo Bills", +1),
      "Brock Purdy": ("San Francisco 49ers", -1), "Jacoby Brissett": ("San Francisco 49ers", +1),
      "Baker Mayfield": ("Tampa Bay Buccaneers", 0), "Kyler Murray": ("Tampa Bay Buccaneers", 0),
      "Kirk Cousins": ("New Orleans Saints", 0), "Tyler Shough": ("New Orleans Saints", 0),
      "Dak Prescott": ("Dallas Cowboys", +1), "Lamar Jackson": ("Dallas Cowboys", -1),
      "Bo Nix": ("Denver Broncos", 0), "Matthew Stafford": ("Denver Broncos", 0)}

rows = []
for _, r in s.iterrows():
    v = V[r.home_team]
    sp, to, cs, ct, tgs, tgt, rs, rt = v
    q = r.q_first if r.two_way else r.imp_first
    mk, pl = r.market_key, r.player_name if isinstance(r.player_name, str) else ""
    if mk == "spreads":
        adj, conf, tag, reason = sp, cs, tgs, rs   # first side = home team
    elif mk == "h2h":
        adj, conf, tag, reason = sp * 0.7, max(5, cs - 25), tgs, "Moneyline follows the spread read: " + rs[:120]
    elif mk == "totals":
        adj, conf, tag, reason = to, ct, tgt, rt
    else:
        # props: first side = Over / Yes
        base = to * 0.6
        tag = "game_script"
        why = "game total lean " + ("over" if to > 0 else "under" if to < 0 else "flat")
        if pl in QB and mk.startswith("player_pass"):
            _, scr = QB[pl]
            if mk in ("player_pass_attempts", "player_pass_completions", "player_pass_yds"):
                base += 0.015 * scr
                why += "; " + ("expected to trail -> more dropbacks" if scr > 0 else "expected to lead -> fewer dropbacks" if scr < 0 else "neutral script")
            if mk == "player_pass_interceptions":
                base = 0.02 * max(scr, 0) + (0.03 if pl == "Jameis Winston" else 0.0) - 0.005
                why = "INT props: " + ("Winston's turnover rate" if pl == "Jameis Winston" else "trailing QB forces throws" if scr > 0 else "default under on INT overs")
        elif pl in QB and mk in ("player_rush_attempts", "player_rush_yds"):
            _, scr = QB[pl]
            base = 0.01 * scr - 0.005
            why = "QB rushing: " + ("scrambles more when trailing" if scr > 0 else "default slight under")
        if base == 0:
            base = -0.006
            why += "; no script signal, default under (prop overs are shaded)"
        if mk == "player_anytime_td":
            base = to * 0.5
            why = "anytime TD follows the game total lean (" + ("over" if to > 0 else "under") + ")"
        adj = base
        conf = int(min(30, 4 + 400 * abs(adj)))
        reason = f"{pl}: {why}."[:160]
    p = float(np.clip(q + adj, 0.02, 0.98))
    if abs(p - q) < 0.002:
        p = q + (0.003 if adj >= 0 else -0.003)
    rows.append({**{k: r[k] for k in ["event_id", "market_key", "player_name", "line"]},
                 "p_first": round(p, 4), "tag": tag, "reason": reason, "conf": conf,
                 "_edge": abs(p - q), "_ct": r.commence_time})
f = pd.DataFrame(rows)
f = f.sort_values(["conf", "_edge", "_ct"], ascending=[False, False, True]).reset_index(drop=True)
f["conf_rank"] = np.arange(1, len(f) + 1)
f.drop(columns=["_edge", "_ct"]).to_csv(f"{S}/wk4_filled.csv", index=False)
print(len(f)); print(f.head(12)[["market_key", "player_name", "line", "p_first", "conf", "conf_rank", "reason"]].to_string())
