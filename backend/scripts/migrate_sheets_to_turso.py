"""Copy every Google Sheet tab into Turso.

Reads through the existing Apps Script `read` action, so no extra Google
credentials are needed — if the app can talk to the sheet, so can this.

Usage (from the repo root):
    uv run python -m backend.scripts.migrate_sheets_to_turso            # migrate all
    uv run python -m backend.scripts.migrate_sheets_to_turso --dry-run  # fetch + report only
    uv run python -m backend.scripts.migrate_sheets_to_turso --only visitors

Re-running is safe: each table is replaced wholesale, so the result always
matches the sheet rather than accumulating duplicates.
"""

import argparse
import sys
from datetime import datetime, timezone

from backend.core.config import logger, TURSO_ENABLED
from backend.utils.sheets import submit_to_sheets, sheets_json
from backend.utils.turso import get_connection, init_schema, check_connection


def _s(value) -> str:
    """Sheet cells arrive as str/int/float/bool/None — normalise to a string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip()


def fetch_sheet(sheet_name: str):
    """Pull all rows of one tab as a list of header-keyed dicts."""
    logger.info("Fetching sheet: %s", sheet_name)
    resp = submit_to_sheets({"action": "read", "sheetName": sheet_name})
    payload = sheets_json(resp)

    if payload is None:
        raise RuntimeError(
            f"Could not read '{sheet_name}' — Apps Script returned no usable JSON. "
            "This is often the intermittent Google delivery failure; retry."
        )
    if not payload.get("success"):
        raise RuntimeError(f"Apps Script error for '{sheet_name}': {payload.get('message')}")

    rows = payload.get("data") or []
    logger.info("  -> %d row(s)", len(rows))
    return rows


# --- Per-sheet loaders -------------------------------------------------------

def migrate_events(conn, rows, dry_run=False):
    """'Event Details' -> events + event_members.

    The sheet repeats an event across rows (one per team member) with only the
    Event ID filled in on continuation rows, so event fields are taken from the
    first row seen for each ID and members are collected separately.
    """
    events, members = {}, []
    for idx, r in enumerate(rows, start=2):  # row 1 is the header
        event_id = _s(r.get("Event ID"))
        if not event_id:
            continue
        if event_id not in events:
            events[event_id] = {
                "event_id": event_id,
                "event_name": _s(r.get("Event Name")),
                "start_date": _s(r.get("Start Date")),
                "end_date": _s(r.get("End Date")),
                "location": _s(r.get("Location")),
                "description": _s(r.get("Description")),
                "created_at": _s(r.get("Timestamp")),
                "source_row": idx,
            }
        name = _s(r.get("Member Name"))
        if name:
            members.append({
                "event_id": event_id,
                "member_name": name,
                "designation": _s(r.get("Designation")),
                "phone": _s(r.get("Phone")),
                "source_row": idx,
            })

    print(f"  events: {len(events)} unique, event_members: {len(members)}")
    if dry_run:
        return len(events)

    conn.execute("DELETE FROM event_members")
    conn.execute("DELETE FROM events")
    for e in events.values():
        conn.execute(
            """INSERT INTO events (event_id,event_name,start_date,end_date,location,
                                   description,created_at,source_row)
               VALUES (?,?,?,?,?,?,?,?)""",
            (e["event_id"], e["event_name"], e["start_date"], e["end_date"],
             e["location"], e["description"], e["created_at"], e["source_row"]),
        )
    for m in members:
        conn.execute(
            """INSERT INTO event_members (event_id,member_name,designation,phone,source_row)
               VALUES (?,?,?,?,?)""",
            (m["event_id"], m["member_name"], m["designation"], m["phone"], m["source_row"]),
        )
    return len(events)


def migrate_cards(conn, rows, dry_run=False):
    """'Event Ai Card' -> event_cards."""
    print(f"  event_cards: {len(rows)}")
    if dry_run:
        return len(rows)

    conn.execute("DELETE FROM event_cards")
    for idx, r in enumerate(rows, start=2):
        conn.execute(
            """INSERT INTO event_cards (
                 event_id,event_name,event_start_date,event_end_date,
                 card_photo_1,card_photo_2,company_name,industry,person_name,designation,
                 phone,email,website,social_media,address,services,company_size,
                 founded_year,registration_status,trust_score,key_people,is_validated,
                 source_link,about_company,location,tag,created_at,source_row
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                _s(r.get("Event ID")), _s(r.get("Event Name")),
                _s(r.get("Event Start Date")), _s(r.get("Event End Date")),
                _s(r.get("Card Photo 1")), _s(r.get("Card Photo 2")),
                _s(r.get("Company Name")), _s(r.get("Industry")),
                _s(r.get("Person Name")), _s(r.get("Designation")),
                _s(r.get("Phone")), _s(r.get("Email")), _s(r.get("Website")),
                _s(r.get("Social Media")), _s(r.get("Address")), _s(r.get("Services")),
                _s(r.get("Company Size")), _s(r.get("Founded Year")),
                _s(r.get("Registration Status")), _s(r.get("Trust Score")),
                _s(r.get("People (Founders)")), _s(r.get("Is Validated")),
                _s(r.get("Source Link")), _s(r.get("About Company")),
                _s(r.get("Location")), _s(r.get("Tag")),
                _s(r.get("Timestamp")), idx,
            ),
        )
    return len(rows)


def migrate_visitors(conn, rows, dry_run=False):
    """'Visitor Details' -> visitors."""
    print(f"  visitors: {len(rows)}")
    if dry_run:
        return len(rows)

    conn.execute("DELETE FROM visitors")
    for idx, r in enumerate(rows, start=2):
        conn.execute(
            """INSERT INTO visitors (
                 event_id,event_name,company_name,customer_name,whatsapp_no,mobile_no,
                 groups,pincode,state,city,address,source,tag,created_at,source_row
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                _s(r.get("Event ID")), _s(r.get("Event Name")),
                _s(r.get("Company Name")), _s(r.get("Customer Name")),
                _s(r.get("WhatsApp No.")), _s(r.get("Mobile No.")),
                _s(r.get("Groups")), _s(r.get("Pincode")),
                _s(r.get("State")), _s(r.get("City")), _s(r.get("Address")),
                _s(r.get("Source")), _s(r.get("Tag")),
                _s(r.get("Timestamp")), idx,
            ),
        )
    return len(rows)


def migrate_profile(conn, rows, dry_run=False):
    """'Company Profile' -> company_profile (last row wins, as the app does)."""
    if not rows:
        print("  company_profile: 0 (sheet empty)")
        return 0
    r = rows[-1]
    print(f"  company_profile: 1 (from last of {len(rows)} row(s))")
    if dry_run:
        return 1

    conn.execute("DELETE FROM company_profile")
    conn.execute(
        """INSERT INTO company_profile (
             id,company_name,tagline,industry,founded_year,official_phone,alternate_phone,
             official_email,whatsapp_number,address_line,city,state,pincode,country,
             website_url,google_maps_link,linkedin,instagram,facebook,twitter,services,
             about_company,key_person_name,key_person_designation,key_person_phone,
             key_person_email,logo_base64,updated_at
           ) VALUES (1,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            _s(r.get("Company Name")), _s(r.get("Tagline")), _s(r.get("Industry")),
            _s(r.get("Founded Year")), _s(r.get("Official Phone")),
            _s(r.get("Alternate Phone")), _s(r.get("Official Email")),
            _s(r.get("WhatsApp Number")), _s(r.get("Address Line 1")),
            _s(r.get("City")), _s(r.get("State")), _s(r.get("Pincode")),
            _s(r.get("Country")), _s(r.get("Website URL")),
            _s(r.get("Google Maps Link")), _s(r.get("LinkedIn")),
            _s(r.get("Instagram")), _s(r.get("Facebook")), _s(r.get("Twitter")),
            _s(r.get("Services Provided")), _s(r.get("About the company")),
            _s(r.get("Key Person Name")), _s(r.get("Key Person Designation")),
            _s(r.get("Key Person Phone")), _s(r.get("Key Person Email")),
            _s(r.get("Logo")), _s(r.get("Timestamp")),
        ),
    )
    return 1


TARGETS = {
    "events":   ("Event Details",  migrate_events),
    "cards":    ("Event Ai Card",  migrate_cards),
    "visitors": ("Visitor Details", migrate_visitors),
    "profile":  ("Company Profile", migrate_profile),
}


def main():
    ap = argparse.ArgumentParser(description="Migrate Google Sheets data into Turso.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Fetch and report counts without writing to Turso.")
    ap.add_argument("--only", choices=sorted(TARGETS), action="append",
                    help="Migrate only this target (repeatable).")
    args = ap.parse_args()

    selected = args.only or list(TARGETS)

    print("=" * 62)
    print("Google Sheets -> Turso migration" + ("  [DRY RUN]" if args.dry_run else ""))
    print("=" * 62)

    conn = None
    if not args.dry_run:
        if not TURSO_ENABLED:
            print("\nERROR: Turso is not configured.")
            print("Set TURSO_DB_URL and TURSO_AUTH_TOKEN in backend/.env, then retry.")
            print("(Use --dry-run to test the Sheets side without Turso.)")
            return 1

        status = check_connection()
        if not status.get("ok"):
            print(f"\nERROR: Turso unreachable — {status.get('reason')}")
            return 1
        print(f"Turso connected. Existing tables: {status.get('tables') or 'none'}")

        if not init_schema():
            print("\nERROR: Could not initialise the Turso schema.")
            return 1
        print("Schema ready.\n")

    # IMPORTANT: fetch from Sheets FIRST, then open a connection per target and
    # commit immediately. Turso drops the connection stream if it sits idle while
    # holding an uncommitted transaction, and an Apps Script read can take 30s+.
    # Holding one connection across all fetch/write cycles fails with
    # "stream not found".
    results, failures = {}, []
    for target in selected:
        sheet_name, loader = TARGETS[target]
        print(f"[{target}] sheet '{sheet_name}'")

        try:
            rows = fetch_sheet(sheet_name)
        except Exception as e:
            print(f"  FAILED (sheet read): {e}")
            failures.append(target)
            continue

        if args.dry_run:
            try:
                results[target] = loader(None, rows, dry_run=True)
            except Exception as e:
                print(f"  FAILED (parse): {e}")
                failures.append(target)
            continue

        conn = None
        try:
            conn = get_connection()
            if conn is None:
                raise RuntimeError("could not open a Turso connection")
            count = loader(conn, rows, dry_run=False)
            conn.execute(
                "INSERT INTO migration_log (sheet_name,row_count,run_at,notes) VALUES (?,?,?,?)",
                (sheet_name, count, datetime.now(timezone.utc).isoformat(), f"target={target}"),
            )
            # Commit before the next (slow) sheet fetch, so no transaction is
            # ever left open across a long network wait.
            conn.commit()
            results[target] = count
            print(f"  committed {count}")
        except Exception as e:
            print(f"  FAILED (write): {type(e).__name__}: {e}")
            failures.append(target)
            if conn is not None:
                try:
                    conn.rollback()
                except Exception:
                    # The stream may already be gone; nothing was committed, so
                    # there is nothing to undo.
                    pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    print("\n" + "=" * 62)
    for target in selected:
        got = results.get(target)
        print(f"  {target:<10} {'FAILED' if target in failures else got}")
    print("=" * 62)

    if failures:
        print(f"\n{len(failures)} target(s) failed: {', '.join(failures)}")
        print("Each target commits independently, so re-run just the failed ones:")
        print(f"  uv run python -m backend.scripts.migrate_sheets_to_turso "
              + " ".join(f"--only {t}" for t in failures))
        return 1
    print("\nDone." if not args.dry_run else "\nDry run complete — nothing written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
