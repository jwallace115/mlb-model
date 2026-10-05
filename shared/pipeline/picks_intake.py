#!/usr/bin/env python3
"""
Member-share intake (human-assisted, v1).

Flow:
  1. Jeff drops Hard Rock share-card screenshots in ~/private_picks/inbox/.
  2. A Claude chat reads each image and writes ~/private_picks/proposed/<drop_utc>_<owner>.json.
  3. Jeff edits and moves to ~/private_picks/confirmed/ adding confirmed_by + confirmed_utc.
  4. Jeff copies to VM: scp ~/private_picks/confirmed/<f>.json do-vm:/root/private/inbox_confirmed/
  5. This script (on VM or Mac dryrun) processes inbox_confirmed/ → ledger, moves to done/.

OPS2 Item 2.
"""
import json, os, sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import picks_ledger as pl
import ticket_id as tk

ROOT = Path(os.environ.get("MLB_REPO_ROOT") or Path(__file__).resolve().parent.parent.parent)
LEDGER_DIR = Path(os.environ.get("PICKS_LEDGER_DIR") or "/root/private/ledger")


def process_inbox(inbox_dir, ledger_dir, resolve_fn=None):
    """Process all JSON files in inbox_dir. Returns summary dict."""
    inbox_dir = Path(inbox_dir)
    ledger_dir = Path(ledger_dir)
    done_dir = inbox_dir / "done"

    if not inbox_dir.exists():
        print(f"inbox {inbox_dir} does not exist")
        return {"appended": 0, "rejected_files": 0, "files": 0}

    members = pl.load_members(ledger_dir)
    files = sorted(inbox_dir.glob("*.json"))
    total_appended = 0
    rejected_files = 0

    for f in files:
        try:
            d = json.loads(f.read_text())
        except Exception as e:
            print(f"REJECT {f.name}: cannot parse JSON ({e})")
            rejected_files += 1
            continue

        # Check confirmed_by and confirmed_utc
        if not d.get("confirmed_by"):
            print(f"REJECT {f.name}: missing confirmed_by")
            rejected_files += 1
            continue
        if not d.get("confirmed_utc"):
            print(f"REJECT {f.name}: missing confirmed_utc")
            rejected_files += 1
            continue

        # Check for UNREADABLE values anywhere in legs
        has_unreadable = False
        for leg in d.get("legs", []):
            for k, v in leg.items():
                if v == "UNREADABLE":
                    print(f"REJECT {f.name}: UNREADABLE value in leg field '{k}'")
                    has_unreadable = True
                    break
            if has_unreadable:
                break
        if has_unreadable:
            rejected_files += 1
            continue

        owner = d.get("owner", "unknown")
        logged_utc = d.get("logged_utc")
        share_link = d.get("share_link")

        # Build ticket_id
        tid = tk.make_ticket_id(
            "ops", str(datetime.now(timezone.utc).date()),
            "member_share", logged_utc)

        rows = []
        file_ok = True
        for i, leg in enumerate(d.get("legs", [])):
            commence = leg.get("commence_time")

            # Check logged < commence
            if logged_utc and commence:
                try:
                    l_dt = pl._parse_utc(logged_utc, "logged")
                    c_dt = pl._parse_utc(commence, "commence")
                    if l_dt >= c_dt:
                        print(f"REJECT {f.name}: logged_utc ({logged_utc}) >= commence_time ({commence})")
                        file_ok = False
                        break
                except (ValueError, TypeError):
                    pass

            # Resolve event_id
            home = leg.get("home")
            away = leg.get("away")
            sport = leg.get("sport", "NFL")

            if resolve_fn:
                event_id, tape_commence = resolve_fn(home, away, commence, sport)
            else:
                from picks_adapters import _resolve_event_id, _sport_folder
                sf = _sport_folder(sport)
                event_id, tape_commence = _resolve_event_id(home, away, commence, sport, sf)

            if tape_commence:
                commence = tape_commence

            row = {
                "ticket_id": tid,
                "owner": owner,
                "source": "member_share",
                "logged_utc": logged_utc,
                "sport": sport,
                "event_id": event_id,
                "commence_time": commence,
                "home": home or "",
                "away": away or "",
                "market": leg.get("market"),
                "player_id": None,
                "player_name": leg.get("player_name"),
                "side": leg.get("side", ""),
                "point": leg.get("point"),
                "price_american": leg.get("price_american"),
                "book": d.get("book"),
                "reason": None,
                "share_link": share_link,
                "supersedes": None,
                "result": None,
                "graded_utc": None,
                "result_source": None,
                "source_file": f.name,
                "source_row": i,
            }
            row["pick_id"] = pl.make_pick_id(
                row["ticket_id"], row["owner"], row["source"], row["event_id"],
                row["market"], row.get("player_name"), row["side"], row.get("point"))
            rows.append(row)

        if not file_ok:
            rejected_files += 1
            continue

        # Admit
        try:
            pl.admit(rows, members)
        except pl.Halt as e:
            print(f"REJECT {f.name}: {e}")
            rejected_files += 1
            continue

        # Append
        appended, skipped = pl.append(rows, ledger_dir)
        total_appended += appended
        print(f"OK {f.name}: {appended} appended, {skipped} skipped")

        # Move to done/
        done_dir.mkdir(exist_ok=True)
        f.rename(done_dir / f.name)

    return {"appended": total_appended, "rejected_files": rejected_files, "files": len(files)}


def main():
    if not LEDGER_DIR.exists():
        print(f"HALT: PICKS_LEDGER_DIR={LEDGER_DIR} does not exist")
        sys.exit(1)

    inbox = Path(os.environ.get("PICKS_INBOX_DIR") or "/root/private/inbox_confirmed")
    result = process_inbox(inbox, LEDGER_DIR)
    print(f"\nfiles: {result['files']}, appended: {result['appended']}, rejected: {result['rejected_files']}")


if __name__ == "__main__":
    main()
