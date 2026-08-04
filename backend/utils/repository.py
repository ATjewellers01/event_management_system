"""Data access for Turso.

This is the whole data layer — reads and writes both go here. Each function
returns header-keyed dicts (like 'Company Name'), which is the shape the frontend
already expected, so moving the backend to Turso needed no UI rewrite.

Connections are reused via `with_connection`. Opening one per call costs ~115ms
of handshake, which dominated query time (500-1000ms per call versus 120-200ms
reused). Reuse is safe here because handlers commit immediately — a connection
is only dropped by the server if it idles holding an OPEN transaction, which is
what broke the migration script, not request handlers.
"""

import asyncio
from datetime import datetime, timezone

from backend.core.config import logger
from backend.utils.turso import with_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _guard(label: str, fn, failure_extra: dict = None):
    """Run a repository operation, turning any failure into a JSON-safe result."""
    try:
        return with_connection(fn)
    except Exception as e:
        logger.error("%s failed: %s: %s", label, type(e).__name__, e)
        out = {"success": False, "message": str(e)}
        if failure_extra:
            out.update(failure_extra)
        return out


# --- Events ------------------------------------------------------------------

def get_event_list() -> dict:
    def op(conn):
        rows = conn.execute(
            """SELECT event_id, event_name, start_date, end_date, location
               FROM events ORDER BY event_id"""
        ).fetchall()
        return {
            "success": True,
            "data": [
                {"id": r[0], "name": r[1], "startDate": r[2],
                 "endDate": r[3], "location": r[4] or ""}
                for r in rows
            ],
        }
    return _guard("get_event_list", op)


def get_event_by_id(event_id: str) -> dict:
    if not event_id:
        return {"success": False, "message": "No Event ID provided"}

    def op(conn):
        rows = conn.execute(
            """SELECT event_id, event_name, start_date, end_date, location,
                      description, created_at
               FROM events WHERE event_id = ?""",
            (event_id,),
        ).fetchall()
        if not rows:
            return {"success": False, "message": "Event not found"}
        r = rows[0]
        members = conn.execute(
            "SELECT member_name, designation, phone FROM event_members WHERE event_id = ?",
            (event_id,),
        ).fetchall()
        # Sheet-style keys, so the existing frontend needs no changes.
        return {
            "success": True,
            "data": {
                "Timestamp": r[6], "Event ID": r[0], "Event Name": r[1],
                "Start Date": r[2], "End Date": r[3], "Location": r[4],
                "Description": r[5],
                "Member Name": members[0][0] if members else "",
                "Designation": members[0][1] if members else "",
                "Phone": members[0][2] if members else "",
                "teamMembers": [
                    {"name": m[0], "designation": m[1], "phone": m[2]} for m in members
                ],
            },
        }
    return _guard("get_event_by_id", op)


def save_event(event_data: dict) -> dict:
    """Insert an event with a sequential EVT-### id, plus its team members."""
    def op(conn):
        existing = conn.execute(
            "SELECT event_id FROM events WHERE event_id LIKE 'EVT-%'"
        ).fetchall()
        highest = 0
        for (eid,) in existing:
            try:
                highest = max(highest, int(str(eid).replace("EVT-", "").strip()))
            except (ValueError, AttributeError):
                continue
        event_id = f"EVT-{highest + 1:03d}"

        conn.execute(
            """INSERT INTO events (event_id,event_name,start_date,end_date,location,
                                   description,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (event_id,
             event_data.get("eventName") or "",
             event_data.get("startDate") or "",
             event_data.get("endDate") or "",
             event_data.get("location") or "",
             event_data.get("description") or "",
             _now()),
        )
        for m in event_data.get("teamMembers") or []:
            conn.execute(
                """INSERT INTO event_members (event_id,member_name,designation,phone)
                   VALUES (?,?,?,?)""",
                (event_id, m.get("name") or "", m.get("designation") or "",
                 m.get("phone") or ""),
            )
        conn.commit()
        return {
            "success": True,
            "message": f"Event '{event_data.get('eventName')}' saved. ID: {event_id}",
            "eventId": event_id,
        }
    return _guard("save_event", op)


def delete_event(event_id: str) -> dict:
    """Delete an event and every card, visitor and member belonging to it."""
    if not event_id:
        return {"success": False, "message": "No Event ID provided"}

    def op(conn):
        deleted = 0
        for table in ("event_members", "event_cards", "visitors"):
            r = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE event_id = ?", (event_id,)
            ).fetchall()
            deleted += r[0][0] if r else 0
            conn.execute(f"DELETE FROM {table} WHERE event_id = ?", (event_id,))
        conn.execute("DELETE FROM events WHERE event_id = ?", (event_id,))
        conn.commit()
        return {
            "success": True,
            "message": f"Event {event_id} and {deleted} related entries deleted successfully",
            "deletedCount": deleted,
        }
    return _guard("delete_event", op)


# --- Column maps (db column -> the header key the frontend reads) ------------

CARD_COLUMNS = [
    ("created_at", "Timestamp"), ("event_id", "Event ID"), ("event_name", "Event Name"),
    ("event_start_date", "Event Start Date"), ("event_end_date", "Event End Date"),
    ("card_photo_1", "Card Photo 1"), ("card_photo_2", "Card Photo 2"),
    ("company_name", "Company Name"), ("industry", "Industry"),
    ("person_name", "Person Name"), ("designation", "Designation"),
    ("phone", "Phone"), ("email", "Email"), ("website", "Website"),
    ("social_media", "Social Media"), ("address", "Address"), ("services", "Services"),
    ("company_size", "Company Size"), ("founded_year", "Founded Year"),
    ("registration_status", "Registration Status"), ("trust_score", "Trust Score"),
    ("key_people", "People (Founders)"), ("is_validated", "Is Validated"),
    ("source_link", "Source Link"), ("about_company", "About Company"),
    ("location", "Location"), ("tag", "Tag"),
]

VISITOR_COLUMNS = [
    ("created_at", "Timestamp"), ("event_id", "Event ID"), ("event_name", "Event Name"),
    ("company_name", "Company Name"), ("customer_name", "Customer Name"),
    ("whatsapp_no", "WhatsApp No."), ("mobile_no", "Mobile No."),
    ("groups", "Groups"), ("pincode", "Pincode"), ("state", "State"),
    ("city", "City"), ("address", "Address"), ("source", "Source"), ("tag", "Tag"),
]


def _select(conn, table: str, colmap: list, where: str = "", params: tuple = ()) -> list:
    """SELECT returning sheet-header-keyed dicts.

    Includes the row id as `_id` so updates target a primary key rather than the
    positional row index the Sheets version depended on.
    """
    cols = ", ".join(c for c, _ in colmap)
    sql = f"SELECT id, {cols} FROM {table}"
    if where:
        sql += f" WHERE {where}"
    sql += " ORDER BY id"
    rows = conn.execute(sql, params).fetchall()
    out = []
    for row in rows:
        d = {"_id": row[0]}
        for i, (_, header) in enumerate(colmap, start=1):
            d[header] = row[i] if row[i] is not None else ""
        out.append(d)
    return out


def get_event_specific_data(event_id: str, event_name: str) -> dict:
    """Cards and visitors for one event — powers the drilldown screen."""
    if not event_id and not event_name:
        return {"success": False, "message": "No Event identifier provided"}
    if event_id:
        where, params = "event_id = ?", (event_id,)
    else:
        where, params = "LOWER(event_name) = LOWER(?)", (event_name,)

    def op(conn):
        return {
            "success": True,
            "cards": _select(conn, "event_cards", CARD_COLUMNS, where, params),
            "visitors": _select(conn, "visitors", VISITOR_COLUMNS, where, params),
        }
    return _guard("get_event_specific_data", op)


def read_table(name: str) -> dict:
    """Whole-table read for the Leads Database page."""
    mapping = {
        "event ai card": ("event_cards", CARD_COLUMNS),
        "visitor details": ("visitors", VISITOR_COLUMNS),
    }
    entry = mapping.get((name or "").strip().lower())
    if entry is None:
        return {"success": False, "message": f"Unknown table '{name}'"}
    table, colmap = entry

    def op(conn):
        return {"success": True, "data": _select(conn, table, colmap)}
    return _guard("read_table", op)


# --- Cards -------------------------------------------------------------------

def _format_key_people(value) -> str:
    """Flatten [{name, role, contact}] into readable lines.

    Stringifying the list directly yields '[object Object]'-style noise.
    """
    if not value:
        return ""
    if isinstance(value, list):
        parts = []
        for p in value:
            if not isinstance(p, dict):
                parts.append(str(p))
                continue
            s = str(p.get("name") or "").strip()
            if p.get("role") and p["role"] != "Not Found":
                s += f" ({p['role']})"
            if p.get("contact") and p["contact"] != "Not Found":
                s += f" - {p['contact']}"
            if s:
                parts.append(s)
        return "\n".join(parts)
    return str(value)


def save_event_card(extracted: dict, photo1_url: str, photo2_url: str,
                    event_info: dict) -> dict:
    d = extracted or {}
    ev = event_info or {}

    # Keep a real False distinguishable from "never checked".
    validated = d.get("is_validated")
    validated_str = "true" if validated is True else ("false" if validated is False else "")

    def op(conn):
        conn.execute(
            """INSERT INTO event_cards (
                 event_id,event_name,event_start_date,event_end_date,
                 card_photo_1,card_photo_2,company_name,industry,person_name,designation,
                 phone,email,website,social_media,address,services,company_size,
                 founded_year,registration_status,trust_score,key_people,is_validated,
                 source_link,about_company,location,tag,created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (ev.get("id") or "", ev.get("name") or "",
             ev.get("startDate") or "", ev.get("endDate") or "",
             photo1_url or "", photo2_url or "",
             d.get("company") or "", d.get("industry") or "",
             d.get("name") or "", d.get("title") or "",
             d.get("phone") or "", d.get("email") or "", d.get("website") or "",
             d.get("social_media") or "", d.get("address") or "", d.get("services") or "",
             d.get("company_size") or "", d.get("founded_year") or "",
             d.get("registration_status") or "", str(d.get("trust_score") or ""),
             _format_key_people(d.get("key_people")), validated_str,
             d.get("validation_source") or "", d.get("about_the_company") or "",
             d.get("location") or "", "", _now()),
        )
        conn.commit()
        return {"success": True, "message": "Card saved to Event Hub!"}
    return _guard("save_event_card", op)


CARD_UPDATE_FIELDS = {
    "Company Name": "company_name", "Industry": "industry",
    "Person Name": "person_name", "Designation": "designation",
    "Phone": "phone", "Email": "email", "Website": "website",
    "Social Media": "social_media", "Address": "address", "Services": "services",
    "Company Size": "company_size", "Founded Year": "founded_year",
    "Location": "location", "About Company": "about_company", "Tag": "tag",
}


def update_card(row_id: int, card_data: dict) -> dict:
    """Update only the fields present in `card_data`.

    Partial updates matter: the inline Tag dropdown sends just {'Tag': ...} and
    must not blank every other column.
    """
    sets, params = [], []
    for header, column in CARD_UPDATE_FIELDS.items():
        if header in card_data:
            sets.append(f"{column} = ?")
            params.append(card_data[header] if card_data[header] is not None else "")
    if not sets:
        return {"success": False, "message": "No updatable fields supplied"}
    params.append(row_id)

    def op(conn):
        conn.execute(f"UPDATE event_cards SET {', '.join(sets)} WHERE id = ?", tuple(params))
        conn.commit()
        return {"success": True, "message": "Card updated successfully"}
    return _guard("update_card", op)


# --- Visitors ----------------------------------------------------------------

def save_visitor(visitor_data: dict) -> dict:
    """Insert a visitor and return the organiser contact for the vCard."""
    event_id = (visitor_data.get("eventId") or "").strip()
    if not event_id:
        return {
            "success": False,
            "message": "Event ID is missing. Please use the correct QR code or link.",
            "contactInfo": None,
        }

    def op(conn):
        ev = conn.execute(
            "SELECT event_name FROM events WHERE event_id = ?", (event_id,)
        ).fetchall()
        event_name = ev[0][0] if ev else "N/A"

        conn.execute(
            """INSERT INTO visitors (
                 event_id,event_name,company_name,customer_name,whatsapp_no,mobile_no,
                 groups,pincode,state,city,address,source,tag,created_at
               ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (event_id, event_name,
             visitor_data.get("companyName") or "",
             visitor_data.get("customerName") or visitor_data.get("visitorName") or "",
             visitor_data.get("whatsappNo") or "",
             visitor_data.get("mobileNo") or visitor_data.get("visitorMobile") or "",
             visitor_data.get("groups") or "",
             visitor_data.get("pincode") or "",
             visitor_data.get("state") or "",
             visitor_data.get("city") or visitor_data.get("visitorCity") or "",
             visitor_data.get("address") or "",
             visitor_data.get("source") or "QR",
             visitor_data.get("tag") or "",
             _now()),
        )
        conn.commit()
        return {
            "success": True,
            "message": "Visitor saved successfully",
            "contactInfo": _contact_from_profile(conn),
        }
    return _guard("save_visitor", op, failure_extra={"contactInfo": None})


VISITOR_UPDATE_FIELDS = {
    "customerName": "customer_name", "companyName": "company_name",
    "mobileNo": "mobile_no", "whatsappNo": "whatsapp_no",
    "groups": "groups", "pincode": "pincode", "state": "state",
    "city": "city", "address": "address", "tag": "tag",
}


def update_visitor(row_id: int, visitor_data: dict) -> dict:
    """Update only the fields present in `visitor_data` (see update_card)."""
    sets, params = [], []
    for key, column in VISITOR_UPDATE_FIELDS.items():
        if key in visitor_data:
            sets.append(f"{column} = ?")
            params.append(visitor_data[key] if visitor_data[key] is not None else "")
    if not sets:
        return {"success": False, "message": "No updatable fields supplied"}
    params.append(row_id)

    def op(conn):
        conn.execute(f"UPDATE visitors SET {', '.join(sets)} WHERE id = ?", tuple(params))
        conn.commit()
        return {"success": True, "message": "Visitor updated successfully"}
    return _guard("update_visitor", op)


# --- Company profile ---------------------------------------------------------

PROFILE_FIELDS = [
    ("company_name", "companyName"), ("tagline", "tagline"), ("industry", "industry"),
    ("founded_year", "foundedYear"), ("official_phone", "officialPhone"),
    ("alternate_phone", "alternatePhone"), ("official_email", "officialEmail"),
    ("whatsapp_number", "whatsappNumber"), ("address_line", "addressLine"),
    ("city", "city"), ("state", "state"), ("pincode", "pincode"),
    ("country", "country"), ("website_url", "websiteUrl"),
    ("google_maps_link", "googleMapsLink"), ("linkedin", "linkedin"),
    ("instagram", "instagram"), ("facebook", "facebook"), ("twitter", "twitter"),
    ("services", "services"), ("about_company", "aboutCompany"),
    ("key_person_name", "keyPersonName"),
    ("key_person_designation", "keyPersonDesignation"),
    ("key_person_phone", "keyPersonPhone"), ("key_person_email", "keyPersonEmail"),
    ("logo_base64", "logoBase64"),
]


def _profile_dict(conn) -> dict:
    cols = ", ".join(c for c, _ in PROFILE_FIELDS)
    rows = conn.execute(f"SELECT {cols} FROM company_profile WHERE id = 1").fetchall()
    if not rows:
        return {}
    return {key: (rows[0][i] or "") for i, (_, key) in enumerate(PROFILE_FIELDS)}


def _contact_from_profile(conn) -> dict:
    """Shape the profile into the contactInfo the visitor vCard expects."""
    p = _profile_dict(conn)
    if not p or not p.get("companyName"):
        return {"name": "Event Organizer", "company": "", "phone": "", "email": "", "website": ""}
    return {
        "name": p.get("keyPersonName") or "Event Organizer",
        "company": p.get("companyName") or "",
        "tagline": p.get("tagline") or "",
        "industry": p.get("industry") or "",
        "foundedYear": p.get("foundedYear") or "",
        "phone": p.get("keyPersonPhone") or p.get("officialPhone") or "N/A",
        "altPhone": p.get("alternatePhone") or "",
        "email": p.get("keyPersonEmail") or p.get("officialEmail") or "N/A",
        "whatsapp": p.get("whatsappNumber") or "",
        "address": p.get("addressLine") or "",
        "city": p.get("city") or "", "state": p.get("state") or "",
        "pincode": p.get("pincode") or "", "country": p.get("country") or "",
        "website": p.get("websiteUrl") or "",
        "mapsLink": p.get("googleMapsLink") or "",
        "linkedin": p.get("linkedin") or "", "instagram": p.get("instagram") or "",
        "facebook": p.get("facebook") or "", "twitter": p.get("twitter") or "",
        "services": p.get("services") or "", "about": p.get("aboutCompany") or "",
        "logoBase64": p.get("logoBase64") or "",
    }


def get_company_profile() -> dict:
    def op(conn):
        return {"success": True, "profile": _profile_dict(conn)}
    return _guard("get_company_profile", op)


def save_company_profile(profile_data: dict) -> dict:
    def op(conn):
        cols = [c for c, _ in PROFILE_FIELDS]
        values = [profile_data.get(key) or "" for _, key in PROFILE_FIELDS]
        placeholders = ",".join("?" for _ in cols)
        # id is pinned to 1, so this replaces the single profile row.
        conn.execute(
            f"""INSERT OR REPLACE INTO company_profile (id,{','.join(cols)},updated_at)
                VALUES (1,{placeholders},?)""",
            tuple(values) + (_now(),),
        )
        conn.commit()
        return {"success": True, "message": "Company profile saved."}
    return _guard("save_company_profile", op)


# --- Async wrapper -----------------------------------------------------------
# libsql is synchronous, so every call is offloaded to a thread to keep it off
# the event loop — the mistake the Sheets version made and paid for.

async def run(fn, *args, **kwargs):
    return await asyncio.to_thread(fn, *args, **kwargs)
