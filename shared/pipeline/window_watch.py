#!/usr/bin/env python3
"""Event-driven watcher: detect input changes and trigger AI reader runs.

VM cron every 5 min. For every upcoming game (kick within 7 days, both sports),
compute an inputs_digest and compare with the digest on the game's newest
ai_reader freeze. TRIGGER when inputs changed significantly.

Triggers:
  - spread moved >= 1.0 pt or total >= 1.0 pt or ML no-vig >= 3 pp (HR or Pinnacle)
  - a new props pull for the event (NFL)
  - injury hash changed (NFL)
  - a new news id tagged to either team (last 5 days)
  - a new sim freeze containing the event
  - no ai_reader read exists yet and kick within 48 h ("horizon entry")

Rate limits:
  - a game is re-read at most once per 30 min UNLESS trigger is injury-hash or kick < 3 h
  - never inside the last 20 min before kick

P62 decision. OPS-CAD1 Item 2.
"""
import gzip
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
PY = sys.executable

# Trigger thresholds
SPREAD_MOVE_THRESHOLD = 1.0
TOTAL_MOVE_THRESHOLD = 1.0
ML_NOVIG_MOVE_PP = 0.03  # 3 percentage points
HORIZON_HOURS = 48
REREAD_MIN = 30  # minutes: rate limit per game
BLACKOUT_MIN = 20  # never read inside last 20 min before kick
LOOKBACK_DAYS = 7


def _parse_utc(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _hash(data):
    """Deterministic hash of a JSON-serializable object."""
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Inputs digest
# ---------------------------------------------------------------------------

def compute_inputs_digest(event_id, sport, root=ROOT, now=None):
    """Compute the inputs digest for one event.

    Components:
      - HR + Pinnacle h2h/spread/total values from newest snapshot
      - newest props pull_timestamp covering the event (NFL)
      - hash of two teams' entries in newest injury file (NFL)
      - set of news ids tagged to either team in last 5 days
      - newest sim freeze id containing the event
      - Kalshi snapshot id

    Returns (digest_hex, components_dict)
    """
    now = now or datetime.now(timezone.utc)
    components = {}

    # 1. Game lines (newest snapshot)
    sport_folder = "ncaaf" if sport == "ncaaf" else "nfl"
    tape_dir = root / "data" / "odds_archive" / sport_folder / "line_history" / "season=2026"
    snaps = sorted(tape_dir.glob("snap_*.parquet")) if tape_dir.exists() else []
    if snaps:
        snap = pd.read_parquet(snaps[-1])
        ev = snap[snap.event_id == event_id]
        for bk in ("hardrockbet_fl", "pinnacle"):
            for mk in ("h2h", "spreads", "totals"):
                rows = ev[(ev.bookmaker == bk) & (ev.market == mk)]
                if not rows.empty:
                    vals = sorted([(r.outcome_name, float(r.point) if pd.notna(r.point) else 0,
                                    int(r.price)) for r in rows.itertuples()])
                    components[f"{bk}_{mk}"] = vals

    # 2. Props pull timestamp (NFL only)
    if sport == "nfl":
        props_dir = root / "data" / "odds_archive" / "nfl" / "props" / "season=2026"
        if props_dir.exists():
            pfiles = sorted(props_dir.glob("month=*/data_*.parquet"))[-2:]
            for pf in pfiles:
                try:
                    df = pd.read_parquet(pf, columns=["event_id", "pull_timestamp"])
                    ev_rows = df[df.event_id == event_id]
                    if not ev_rows.empty:
                        components["props_ts"] = str(ev_rows.pull_timestamp.max())
                except Exception:
                    pass

    # 3. Injury hash (NFL only)
    if sport == "nfl":
        inj_dir = root / "data" / "injury_archive" / "nfl" / "season=2026"
        if inj_dir.exists():
            inj_files = sorted(inj_dir.glob("injuries_*.json.gz"))
            if inj_files:
                try:
                    d = json.load(gzip.open(str(inj_files[-1]), "rt"))
                    # We need the teams for this event from the snapshot
                    if snaps:
                        ev = snap[snap.event_id == event_id]
                        if not ev.empty:
                            home = ev.home_team.iloc[0]
                            away = ev.away_team.iloc[0]
                            inj_data = {t["displayName"]: t["injuries"]
                                        for t in d.get("injuries", [])}
                            for team in (home, away):
                                team_inj = inj_data.get(team, [])
                                components[f"inj_{team}"] = _hash(team_inj)
                except Exception:
                    pass

    # 4. News ids (last 5 days)
    news_dir = root / "data" / "news_archive" / sport_folder / "season=2026"
    if news_dir.exists() and snaps:
        ev = snap[snap.event_id == event_id]
        if not ev.empty:
            home = ev.home_team.iloc[0]
            away = ev.away_team.iloc[0]
            news_ids = set()
            for f in sorted(news_dir.glob("news_*"))[-20:]:
                try:
                    items = json.load(gzip.open(str(f), "rt"))
                except Exception:
                    continue
                for it in items:
                    teams = {c.get("description") for c in it.get("categories", [])
                             if c.get("type") == "team"}
                    if teams & {home, away}:
                        news_ids.add(it.get("headline", "")[:50])
            if news_ids:
                components["news"] = sorted(news_ids)

    # 5. Sim freeze id
    for wd in sorted((root / "nfl" / "data" / "board").glob("week=2026_*/ai_opinions/manifest.json"))[-2:]:
        try:
            m = json.load(open(wd))
            sims = [e for e in m if (e.get("reader_model") or "").startswith("nfl_sim")]
            if sims:
                fp = wd.parent / sims[-1]["file"]
                if fp.exists():
                    df = pd.read_parquet(fp, columns=["event_id"])
                    if event_id in df.event_id.values:
                        components["sim_freeze"] = sims[-1]["file"]
        except Exception:
            pass

    # 6. Kalshi snapshot id
    kalshi_dir = root / "data" / "odds_archive" / "kalshi" / sport_folder / "season=2026"
    if kalshi_dir.exists():
        ks = sorted(kalshi_dir.glob("snap_*.parquet"))
        if ks:
            components["kalshi_snap"] = os.path.basename(str(ks[-1]))

    digest = _hash(components)
    return digest, components


def get_last_read_digest(event_id, sport, root=ROOT):
    """Get the inputs_digest from the most recent ai_reader freeze for this event.

    Returns (digest_or_None, logged_utc_or_None, reader_model_or_None)
    """
    sport_board = "ncaaf" if sport == "ncaaf" else "nfl"
    board_dir = root / sport_board / "data" / "board"
    best_logged = None
    best_digest = None
    best_model = None

    for wd in sorted(board_dir.glob(f"week=2026_*/ai_opinions/manifest.json")):
        try:
            entries = json.loads(wd.read_text())
        except Exception:
            continue
        for e in entries:
            rm = e.get("reader_model", "")
            if not rm.startswith("ai_reader_v1"):
                continue
            inputs = e.get("inputs", {})
            digest = inputs.get("inputs_digest")
            logged = e.get("logged_utc")
            # Check if this freeze covers the event
            fp = wd.parent / e["file"]
            if fp.exists():
                try:
                    df = pd.read_parquet(fp, columns=["event_id"])
                    if event_id not in df.event_id.values:
                        continue
                except Exception:
                    continue
            if logged and (best_logged is None or logged > best_logged):
                best_logged = logged
                best_digest = digest
                best_model = rm

    return best_digest, best_logged, best_model


# ---------------------------------------------------------------------------
# Trigger detection
# ---------------------------------------------------------------------------

def _line_values_from_digest(components, book, market):
    """Extract (point, price) tuples from digest components for comparison."""
    key = f"{book}_{market}"
    vals = components.get(key, [])
    return {name: (pt, price) for name, pt, price in vals}


def detect_triggers(event_id, sport, current_digest, current_components,
                    last_digest, last_components, last_logged_utc,
                    commence_time, now):
    """Detect all trigger reasons for a game.

    Returns list of trigger strings, or empty list if no trigger.
    """
    triggers = []
    kick = _parse_utc(commence_time)
    hours_to_kick = (kick - now).total_seconds() / 3600

    # Blackout: never inside last 20 min before kick
    if hours_to_kick < BLACKOUT_MIN / 60:
        return []

    # No prior read + within horizon
    if last_digest is None:
        if hours_to_kick <= HORIZON_HOURS:
            triggers.append(f"horizon_entry: kick in {hours_to_kick:.0f}h, no prior read")
        return triggers

    # Digest unchanged → no trigger
    if current_digest == last_digest:
        return []

    # Rate limit: 30 min unless injury or kick < 3h
    if last_logged_utc:
        age_min = (now - _parse_utc(last_logged_utc)).total_seconds() / 60
    else:
        age_min = float("inf")

    # Compare line moves
    for book in ("hardrockbet_fl", "pinnacle"):
        for mk, threshold in [("spreads", SPREAD_MOVE_THRESHOLD),
                               ("totals", TOTAL_MOVE_THRESHOLD)]:
            old = _line_values_from_digest(last_components or {}, book, mk)
            new = _line_values_from_digest(current_components, book, mk)
            for name in set(old) | set(new):
                if name in old and name in new:
                    old_pt = old[name][0]
                    new_pt = new[name][0]
                    if abs(new_pt - old_pt) >= threshold:
                        triggers.append(f"line_move: {book} {mk} {name} {old_pt}→{new_pt}")

        # ML no-vig move
        old_ml = _line_values_from_digest(last_components or {}, book, "h2h")
        new_ml = _line_values_from_digest(current_components, book, "h2h")
        if old_ml and new_ml:
            old_prices = list(old_ml.values())
            new_prices = list(new_ml.values())
            if len(old_prices) >= 2 and len(new_prices) >= 2:
                old_imp = [_implied_from_price(p[1]) for p in old_prices]
                new_imp = [_implied_from_price(p[1]) for p in new_prices]
                if old_imp[0] + old_imp[1] > 0 and new_imp[0] + new_imp[1] > 0:
                    old_nv = old_imp[0] / (old_imp[0] + old_imp[1])
                    new_nv = new_imp[0] / (new_imp[0] + new_imp[1])
                    if abs(new_nv - old_nv) >= ML_NOVIG_MOVE_PP:
                        triggers.append(f"ml_move: {book} novig {old_nv:.3f}→{new_nv:.3f}")

    # Props pull (NFL only)
    if sport == "nfl":
        old_ts = (last_components or {}).get("props_ts")
        new_ts = current_components.get("props_ts")
        if new_ts and new_ts != old_ts:
            triggers.append(f"new_props: pull {new_ts}")

    # Injury hash change
    if sport == "nfl":
        for key in current_components:
            if key.startswith("inj_"):
                old_h = (last_components or {}).get(key)
                new_h = current_components[key]
                if old_h != new_h:
                    triggers.append(f"injury_change: {key}")

    # News change
    old_news = set((last_components or {}).get("news", []))
    new_news = set(current_components.get("news", []))
    new_items = new_news - old_news
    if new_items:
        triggers.append(f"new_news: {len(new_items)} items")

    # Sim freeze change
    old_sim = (last_components or {}).get("sim_freeze")
    new_sim = current_components.get("sim_freeze")
    if new_sim and new_sim != old_sim:
        triggers.append(f"new_sim: {new_sim}")

    if not triggers:
        return []

    # Rate limit enforcement
    is_injury = any("injury" in t for t in triggers)
    is_urgent = hours_to_kick < 3
    if age_min < REREAD_MIN and not is_injury and not is_urgent:
        return []  # rate limited

    return triggers


def _implied_from_price(price):
    """American price → implied probability."""
    p = float(price)
    return 100.0 / (p + 100.0) if p > 0 else -p / (-p + 100.0)


# ---------------------------------------------------------------------------
# Upcoming games
# ---------------------------------------------------------------------------

def get_upcoming_games(sport, root=ROOT, now=None, lookback_days=LOOKBACK_DAYS):
    """Get upcoming games (kick within lookback_days) from the tape.

    Returns list of (event_id, home_team, away_team, commence_time).
    """
    now = now or datetime.now(timezone.utc)
    sport_folder = "ncaaf" if sport == "ncaaf" else "nfl"
    tape_dir = root / "data" / "odds_archive" / sport_folder / "line_history" / "season=2026"
    if not tape_dir.exists():
        return []
    snaps = sorted(tape_dir.glob("snap_*.parquet"))
    if not snaps:
        return []
    snap = pd.read_parquet(snaps[-1])
    snap = snap.drop_duplicates("event_id")
    cutoff = now + timedelta(days=lookback_days)
    games = []
    for _, r in snap.iterrows():
        try:
            ct = _parse_utc(r.commence_time)
        except Exception:
            continue
        if ct > now and ct < cutoff:
            games.append((r.event_id, r.home_team, r.away_team, str(r.commence_time)))
    return games


# ---------------------------------------------------------------------------
# Main watcher loop (one tick)
# ---------------------------------------------------------------------------

def _newest_props_ts(event_id, root):
    """Return the newest pull_timestamp for an event from the props archive, or None."""
    props_dir = root / "data" / "odds_archive" / "nfl" / "props" / "season=2026"
    if not props_dir.exists():
        return None
    pfiles = sorted(props_dir.glob("month=*/data_*.parquet"))[-2:]
    best = None
    for pf in pfiles:
        try:
            df = pd.read_parquet(pf, columns=["event_id", "pull_timestamp"])
            ev = df[df.event_id == event_id]
            if not ev.empty:
                ts = str(ev.pull_timestamp.max())
                if best is None or ts > best:
                    best = ts
        except Exception:
            pass
    return best


def _should_pull_props(eid, sport, ct_str, now, root,
                       has_injury_trigger=False, has_news_trigger=False,
                       has_horizon_trigger=False):
    """P63/CAD1b: decide whether to pull props for this event.

    Returns True if any of:
      - no pull for the event yet and kick <= 48 h (horizon)
      - injury-hash or new-news trigger fired
      - kick <= 2 h and newest pull > 60 min old
      - kick <= 45 min and newest pull > 20 min old (close pull)
    """
    if sport != "nfl":
        return False
    kick = _parse_utc(ct_str)
    hours_to_kick = (kick - now).total_seconds() / 3600
    if hours_to_kick <= 0:
        return False

    newest_ts = _newest_props_ts(eid, root)
    pull_age_min = float("inf")
    if newest_ts:
        try:
            pull_age_min = (now - _parse_utc(newest_ts)).total_seconds() / 60
        except Exception:
            pass

    # Horizon: no pull yet and kick <= 48h
    if newest_ts is None and hours_to_kick <= HORIZON_HOURS:
        return True
    if has_horizon_trigger and newest_ts is None:
        return True

    # Injury or news trigger
    if has_injury_trigger or has_news_trigger:
        return True

    # Kick <= 2h and pull > 60 min old
    if hours_to_kick <= 2 and pull_age_min > 60:
        return True

    # Kick <= 45 min and pull > 20 min old (close pull)
    if hours_to_kick <= 0.75 and pull_age_min > 20:
        return True

    return False


def _run_props_pull(event_ids, root, dry_run=False):
    """Run pull_hardrock_props.py --events for the given event IDs.

    Returns True if the pull succeeded (or was skipped on credit HALT).
    """
    if not event_ids or dry_run:
        return True
    puller = root / "nfl" / "pipeline" / "pull_hardrock_props.py"
    if not puller.exists():
        print(f"  WARNING: props puller not found at {puller}")
        return False
    cmd = [
        sys.executable, str(puller),
        "--events", ",".join(event_ids),
        "--tag", "event",
        "--window-hours", "168",
        "--archive",
    ]
    print(f"  props pull: {len(event_ids)} events")
    result = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        stderr = result.stderr[:200] if result.stderr else ""
        if "HALT" in (result.stdout or "") or "HALT" in stderr:
            print(f"  props pull HALT (credit limit) — read continues on older pull")
            return True  # not fatal; read on older data
        print(f"  props pull exit {result.returncode}: {stderr}")
        return False
    # Print credits line if available
    for line in (result.stdout or "").splitlines():
        if "credits" in line.lower() or "remaining" in line.lower():
            print(f"  {line.strip()}")
    return True


def watch_once(sport, root=ROOT, now=None, dry_run=False):
    """Run one watcher tick.

    Returns (triggered_games, trigger_details) where:
      triggered_games = list of event_ids
      trigger_details = dict of {event_id: [trigger_strings]}
    """
    now = now or datetime.now(timezone.utc)
    games = get_upcoming_games(sport, root=root, now=now)
    if not games:
        print(f"  {sport}: no upcoming games")
        return [], {}

    # ── Phase 1: pre-trigger scan to identify props pull candidates ──
    # Do a quick scan for injury/news/horizon triggers BEFORE pulling props
    pull_candidates = []
    pre_triggers = {}  # eid -> preliminary trigger info
    for eid, home, away, ct in games:
        # Quick check: does this game need a props pull?
        # We need a preliminary trigger scan for injury/news
        digest, components = compute_inputs_digest(eid, sport, root=root, now=now)
        last_digest, last_logged, _ = get_last_read_digest(eid, sport, root=root)
        last_components = _load_last_components(eid, sport, root)

        # Check for injury/news changes
        has_injury = False
        has_news = False
        has_horizon = (last_digest is None)
        if last_components:
            for key in components:
                if key.startswith("inj_") and components[key] != (last_components or {}).get(key):
                    has_injury = True
            old_news = set((last_components or {}).get("news", []))
            new_news = set(components.get("news", []))
            if new_news - old_news:
                has_news = True

        pre_triggers[eid] = {"injury": has_injury, "news": has_news, "horizon": has_horizon}

        if _should_pull_props(eid, sport, ct, now, root,
                              has_injury_trigger=has_injury,
                              has_news_trigger=has_news,
                              has_horizon_trigger=has_horizon):
            pull_candidates.append(eid)

    # ── Phase 1b: run props pulls (NFL only) ──
    if pull_candidates and sport == "nfl":
        _run_props_pull(pull_candidates, root, dry_run=dry_run)

    # ── Phase 2: compute digests AFTER pulls and detect triggers ──
    triggered = []
    details = {}
    for eid, home, away, ct in games:
        digest, components = compute_inputs_digest(eid, sport, root=root, now=now)
        last_digest, last_logged, _ = get_last_read_digest(eid, sport, root=root)
        last_components = _load_last_components(eid, sport, root)

        triggers = detect_triggers(
            eid, sport, digest, components,
            last_digest, last_components, last_logged,
            ct, now)

        if triggers:
            triggered.append(eid)
            details[eid] = triggers
            print(f"  TRIGGER {eid} ({away} @ {home}): {'; '.join(triggers)}")

    if not triggered:
        print(f"  {sport}: no triggers ({len(games)} games checked)")

    return triggered, details


def _load_last_components(event_id, sport, root):
    """Load the full components dict from the last ai_reader freeze for comparison."""
    sport_board = "ncaaf" if sport == "ncaaf" else "nfl"
    board_dir = root / sport_board / "data" / "board"
    best_logged = None
    best_components = None

    for wd in sorted(board_dir.glob(f"week=2026_*/ai_opinions/manifest.json")):
        try:
            entries = json.loads(wd.read_text())
        except Exception:
            continue
        for e in entries:
            rm = e.get("reader_model", "")
            if not rm.startswith("ai_reader_v1"):
                continue
            inputs = e.get("inputs", {})
            logged = e.get("logged_utc")
            # Check if this freeze covers the event
            fp = wd.parent / e["file"]
            if fp.exists():
                try:
                    df = pd.read_parquet(fp, columns=["event_id"])
                    if event_id not in df.event_id.values:
                        continue
                except Exception:
                    continue
            if logged and (best_logged is None or logged > best_logged):
                best_logged = logged
                # The components are stored as the inputs dict
                best_components = inputs

    return best_components


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Event-driven watcher")
    ap.add_argument("--sport", default="nfl", choices=["nfl", "ncaaf"])
    ap.add_argument("--once", action="store_true", help="run one tick and exit")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--root", default=str(ROOT))
    args = ap.parse_args()

    root = Path(args.root)
    now = datetime.now(timezone.utc)
    ts = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[{ts}] window_watch tick: sport={args.sport}")

    triggered, details = watch_once(args.sport, root=root, now=now, dry_run=args.dry_run)

    if not triggered:
        # Write health
        _write_health(args.sport, "event", "no_triggers", root=root)
        return

    if args.dry_run:
        print(f"  dry run: {len(triggered)} games would be read")
        return

    # Build trigger text for each event
    trigger_text = {eid: "; ".join(details[eid]) for eid in triggered}

    # Run the AI reader
    from shared.pipeline import ai_reader as ar
    sys.path.insert(0, str(root / "nfl" / "pipeline"))
    import log_ai_opinions as lao
    lao.set_sport(args.sport)
    from nfl.pipeline.current_week import current_week
    week, _ = current_week(args.sport, root=root)

    # Resolve inputs
    props_path, lines_path = lao.resolve_inputs(2026, now)

    # Build sheet
    props, lines = lao.newest_inputs(2026, now, props_file=props_path, lines_file=lines_path)
    sheet = lao.build_sheet(props, lines, now)

    # Build packets
    header, packets = ar.build_packet(
        args.sport, triggered, sheet, props, lines, now,
        root=root, triggers=trigger_text)

    # Save packet
    freeze_dir = lao.out_dir(2026, week)
    freeze_dir.mkdir(parents=True, exist_ok=True)
    pkt_ts = now.strftime("%Y%m%dT%H%M%SZ")
    pkt_path = freeze_dir / f"packet_{pkt_ts}.txt"
    pkt_path.write_text(header + "\n\n" + "\n\n".join(packets.values()))

    # Read each game
    model = os.environ.get("AI_READER_MODEL", ar.DEFAULT_MODEL)
    all_picks = []
    for eid in triggered:
        if eid not in packets:
            continue
        game_sheet = sheet[sheet.event_id == eid]
        if game_sheet.empty:
            continue
        try:
            picks, in_tok, out_tok = ar.read_game(
                packets[eid], game_sheet, args.sport,
                model=model, root=root)
            all_picks.extend(picks)
            print(f"  read {eid}: {len(picks)} picks, {in_tok}/{out_tok} tokens")
        except Exception as e:
            print(f"  HALT for {eid}: {e}")
            continue

    if not all_picks:
        print("  no picks from any game — skipping freeze")
        _write_health(args.sport, "event", "no_picks", root=root)
        return

    # Convert and freeze
    filled = ar.picks_to_filled(all_picks, sheet[sheet.event_id.isin(set(triggered))], args.sport)
    reader_model = f"ai_reader_v1b/{model}"

    # Compute digest for each event
    digests = {}
    for eid in triggered:
        d, _ = compute_inputs_digest(eid, args.sport, root=root, now=now)
        digests[eid] = d

    dest, sha, frozen = ar.freeze_reads(
        filled, args.sport, 2026, week, now,
        window="event", reader_model=reader_model, root=root,
        triggers=trigger_text, props_file=props_path, lines_file=lines_path,
        inputs_digest=json.dumps(digests))

    print(f"  FROZEN: {dest.name} sha={sha[:16]} rows={len(frozen)}")

    # Post-freeze: run adapters + top20 + site build
    env = dict(os.environ)
    env["MLB_REPO_ROOT"] = str(root)
    sport_upper = args.sport.upper()

    for desc, cmd in [
        ("picks_adapters", [PY, str(root / "shared" / "pipeline" / "picks_adapters.py")]),
        ("pick_layers --build-missing", [PY, str(root / "shared" / "pipeline" / "pick_layers.py"),
                                         "--build-missing"]),
        ("build_site", [PY, str(root / "site" / "build_site.py")]),
    ]:
        print(f"  {desc}...")
        result = subprocess.run(cmd, cwd=str(root), env=env,
                                capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            print(f"  WARNING: {desc} exit {result.returncode}: {result.stderr[:200]}")

    # Write health
    _write_health(args.sport, "event", "COMPLETE",
                  freeze_file=dest.name, root=root,
                  triggers=list(trigger_text.values()))

    spend = ar._load_spend(root)
    print(f"  spend: {json.dumps(spend)}")
    print(f"  odds credits: {_read_odds_credits(root)}")


def write_sim_requests(sport, event_ids, reasons, root=ROOT):
    """P64: write status/sim_requests.json for the Mac tick."""
    status_dir = root / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    path = status_dir / "sim_requests.json"
    try:
        existing = json.loads(path.read_text()) if path.exists() else []
    except Exception:
        existing = []
    now = datetime.now(timezone.utc)
    for eid in event_ids:
        # Don't duplicate
        if any(r.get("event_id") == eid and r.get("sport") == sport for r in existing):
            continue
        existing.append({
            "sport": sport,
            "event_id": eid,
            "reason": reasons.get(eid, "trigger"),
            "requested_utc": now.isoformat(),
        })
    path.write_text(json.dumps(existing, indent=1) + "\n")


def _write_health(sport, window, result, freeze_file=None, root=ROOT, triggers=None):
    """Write status/window_health.json for the event window."""
    status_dir = root / "status"
    status_dir.mkdir(parents=True, exist_ok=True)
    health_path = status_dir / "window_health.json"
    try:
        entries = json.loads(health_path.read_text()) if health_path.exists() else []
    except Exception:
        entries = []
    now = datetime.now(timezone.utc)
    entry = {
        "sport": sport, "window": window,
        "started_utc": now.isoformat(), "finished_utc": now.isoformat(),
        "result": result, "step": "window_watch",
        "message": str(triggers)[:200] if triggers else "",
        "freeze_file": freeze_file,
    }
    entries = [e for e in entries if not (e.get("sport") == sport and e.get("window") == window)]
    entries.append(entry)
    health_path.write_text(json.dumps(entries, indent=1) + "\n")


def _read_odds_credits(root):
    """Read odds credits status if available."""
    p = root / "status" / "odds_credits.json"
    if p.exists():
        return json.loads(p.read_text())
    return {}


if __name__ == "__main__":
    main()
