"""Turso (libSQL) connection and schema.

The schema mirrors the Google Sheets tabs so the migration is a straight copy and
the app can read from either backend during the trial. Sheet header names map to
snake_case columns; `source_row` keeps the original sheet row number so a record
can still be traced back to the spreadsheet after migrating.

Everything here fails soft: if Turso is not configured, `get_connection()`
returns None and callers fall back to Sheets rather than erroring.
"""

import asyncio
import threading
from typing import Optional

from backend.core.config import (
    logger, TURSO_DB_URL, TURSO_AUTH_TOKEN, TURSO_ENABLED,
)

try:
    import libsql
except ImportError:  # pragma: no cover - dependency is optional at runtime
    libsql = None
    logger.warning("libsql not installed — Turso support unavailable.")


SCHEMA_STATEMENTS = [
    # --- Events (from the "Event Details" sheet) ---
    # One sheet row per team member, so events repeat across rows there. Here the
    # event is stored once and members live in their own table.
    """
    CREATE TABLE IF NOT EXISTS events (
        event_id     TEXT PRIMARY KEY,
        event_name   TEXT NOT NULL DEFAULT '',
        start_date   TEXT DEFAULT '',
        end_date     TEXT DEFAULT '',
        location     TEXT DEFAULT '',
        description  TEXT DEFAULT '',
        created_at   TEXT DEFAULT '',
        source_row   INTEGER
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS event_members (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id     TEXT NOT NULL,
        member_name  TEXT DEFAULT '',
        designation  TEXT DEFAULT '',
        phone        TEXT DEFAULT '',
        source_row   INTEGER,
        FOREIGN KEY (event_id) REFERENCES events(event_id) ON DELETE CASCADE
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_event_members_event ON event_members(event_id)",

    # --- Scanned business cards (from the "Event Ai Card" sheet) ---
    """
    CREATE TABLE IF NOT EXISTS event_cards (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id            TEXT DEFAULT '',
        event_name          TEXT DEFAULT '',
        event_start_date    TEXT DEFAULT '',
        event_end_date      TEXT DEFAULT '',
        card_photo_1        TEXT DEFAULT '',
        card_photo_2        TEXT DEFAULT '',
        company_name        TEXT DEFAULT '',
        industry            TEXT DEFAULT '',
        person_name         TEXT DEFAULT '',
        designation         TEXT DEFAULT '',
        phone               TEXT DEFAULT '',
        email               TEXT DEFAULT '',
        website             TEXT DEFAULT '',
        social_media        TEXT DEFAULT '',
        address             TEXT DEFAULT '',
        services            TEXT DEFAULT '',
        company_size        TEXT DEFAULT '',
        founded_year        TEXT DEFAULT '',
        registration_status TEXT DEFAULT '',
        trust_score         TEXT DEFAULT '',
        key_people          TEXT DEFAULT '',
        is_validated        TEXT DEFAULT '',
        source_link         TEXT DEFAULT '',
        about_company       TEXT DEFAULT '',
        location            TEXT DEFAULT '',
        tag                 TEXT DEFAULT '',
        created_at          TEXT DEFAULT '',
        source_row          INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_event_cards_event ON event_cards(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_event_cards_company ON event_cards(company_name)",

    # --- Visitors (from the "Visitor Details" sheet) ---
    """
    CREATE TABLE IF NOT EXISTS visitors (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id      TEXT DEFAULT '',
        event_name    TEXT DEFAULT '',
        company_name  TEXT DEFAULT '',
        customer_name TEXT DEFAULT '',
        whatsapp_no   TEXT DEFAULT '',
        mobile_no     TEXT DEFAULT '',
        groups        TEXT DEFAULT '',
        pincode       TEXT DEFAULT '',
        state         TEXT DEFAULT '',
        city          TEXT DEFAULT '',
        address       TEXT DEFAULT '',
        source        TEXT DEFAULT '',
        tag           TEXT DEFAULT '',
        created_at    TEXT DEFAULT '',
        source_row    INTEGER
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_visitors_event ON visitors(event_id)",
    "CREATE INDEX IF NOT EXISTS idx_visitors_mobile ON visitors(mobile_no)",

    # --- Company profile (from the "Company Profile" sheet) ---
    # A single logical record; id is pinned to 1 so upserts always replace it.
    """
    CREATE TABLE IF NOT EXISTS company_profile (
        id                      INTEGER PRIMARY KEY CHECK (id = 1),
        company_name            TEXT DEFAULT '',
        tagline                 TEXT DEFAULT '',
        industry                TEXT DEFAULT '',
        founded_year            TEXT DEFAULT '',
        official_phone          TEXT DEFAULT '',
        alternate_phone         TEXT DEFAULT '',
        official_email          TEXT DEFAULT '',
        whatsapp_number         TEXT DEFAULT '',
        address_line            TEXT DEFAULT '',
        city                    TEXT DEFAULT '',
        state                   TEXT DEFAULT '',
        pincode                 TEXT DEFAULT '',
        country                 TEXT DEFAULT '',
        website_url             TEXT DEFAULT '',
        google_maps_link        TEXT DEFAULT '',
        linkedin                TEXT DEFAULT '',
        instagram               TEXT DEFAULT '',
        facebook                TEXT DEFAULT '',
        twitter                 TEXT DEFAULT '',
        services                TEXT DEFAULT '',
        about_company           TEXT DEFAULT '',
        key_person_name         TEXT DEFAULT '',
        key_person_designation  TEXT DEFAULT '',
        key_person_phone        TEXT DEFAULT '',
        key_person_email        TEXT DEFAULT '',
        logo_base64             TEXT DEFAULT '',
        updated_at              TEXT DEFAULT ''
    )
    """,

    # Bookkeeping for migration runs, so a re-run is auditable.
    """
    CREATE TABLE IF NOT EXISTS migration_log (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        sheet_name TEXT NOT NULL,
        row_count  INTEGER NOT NULL,
        run_at     TEXT NOT NULL,
        notes      TEXT DEFAULT ''
    )
    """,
]


def get_connection():
    """Open a NEW Turso connection, or return None if unavailable.

    Prefer `with_connection()` in request paths — the handshake costs ~115ms, so
    opening one per call dominates query time (measured: 500-1000ms per call
    versus 120-200ms when the connection is reused).

    Never raises: a Turso problem should surface as a handled error, not a crash.
    """
    if not TURSO_ENABLED:
        return None
    if libsql is None:
        logger.error("Turso is configured but the libsql package is not installed.")
        return None
    try:
        return libsql.connect(database=TURSO_DB_URL, auth_token=TURSO_AUTH_TOKEN)
    except Exception as e:
        logger.error("Turso connection failed: %s: %s", type(e).__name__, e)
        return None


# A single shared connection, reused across requests to skip the handshake.
# Safe because request handlers commit immediately: a connection only gets
# dropped by the server ("stream not found") if it idles while holding an OPEN
# transaction, which is what broke the migration script. Verified to survive a
# 40s idle gap with no transaction open.
_shared_conn = None
_conn_lock = threading.Lock()


def with_connection(fn):
    """Run fn(conn) on the shared connection, reconnecting once if it went stale.

    Serialised with a lock: libsql connections are not documented as
    thread-safe, and handlers run in worker threads via asyncio.to_thread.
    """
    global _shared_conn

    if not TURSO_ENABLED:
        raise RuntimeError("Turso is not configured (need TURSO_DB_URL and TURSO_AUTH_TOKEN)")

    with _conn_lock:
        for attempt in (1, 2):
            if _shared_conn is None:
                _shared_conn = get_connection()
                if _shared_conn is None:
                    raise RuntimeError("Could not open a Turso connection")
            try:
                return fn(_shared_conn)
            except Exception as e:
                # A dropped stream is recoverable; reconnect and retry once.
                stale = "stream not found" in str(e).lower() or "hrana" in str(e).lower()
                if attempt == 1 and stale:
                    logger.warning("Turso connection went stale — reconnecting: %s", e)
                    try:
                        _shared_conn.close()
                    except Exception:
                        pass
                    _shared_conn = None
                    continue
                raise


def init_schema(conn=None) -> bool:
    """Create tables and indexes if they don't exist. Returns True on success."""
    own_conn = conn is None
    conn = conn or get_connection()
    if conn is None:
        logger.error("Cannot init schema — no Turso connection.")
        return False
    try:
        for stmt in SCHEMA_STATEMENTS:
            conn.execute(stmt)
        conn.commit()
        logger.info("Turso schema ready (%d statements).", len(SCHEMA_STATEMENTS))
        return True
    except Exception as e:
        logger.error("Turso schema init failed: %s: %s", type(e).__name__, e)
        return False
    finally:
        if own_conn:
            try:
                conn.close()
            except Exception:
                pass


def check_connection() -> dict:
    """Diagnostic used by the health endpoint and the migration script."""
    if not TURSO_ENABLED:
        missing = []
        if not TURSO_DB_URL:
            missing.append("TURSO_DB_URL")
        if not TURSO_AUTH_TOKEN:
            missing.append("TURSO_AUTH_TOKEN")
        return {"ok": False, "reason": f"not configured (missing: {', '.join(missing)})"}

    conn = get_connection()
    if conn is None:
        return {"ok": False, "reason": "connection failed — see logs"}
    try:
        conn.execute("SELECT 1")
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        return {"ok": True, "tables": [t[0] for t in tables]}
    except Exception as e:
        return {"ok": False, "reason": f"{type(e).__name__}: {e}"}
    finally:
        try:
            conn.close()
        except Exception:
            pass


async def check_connection_async() -> dict:
    """Thread-offloaded variant for use inside async request handlers."""
    return await asyncio.to_thread(check_connection)
