import sqlite3
import os
import re
from datetime import datetime, timezone

DEFAULT_DB_PATH = os.environ.get("DATABASE_PATH", "responza.db")

def mask_phone_number(phone: str) -> str:
    """
    Mask phone number for privacy protection (e.g. +918499955374 -> +918****5374)
    """
    if not phone:
        return "Unknown"
    phone_clean = str(phone).strip()
    if len(phone_clean) <= 6:
        return "****"
    # Keep first 4 and last 4 characters visible, mask middle
    visible_prefix = phone_clean[:4]
    visible_suffix = phone_clean[-4:]
    masked_middle = "*" * max(3, len(phone_clean) - 8)
    return f"{visible_prefix}{masked_middle}{visible_suffix}"

def get_db_connection(db_path: str = None):
    """Establish and return SQLite database connection with row factory."""
    path = db_path or os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db(db_path: str = None):
    """Initialize database tables with schema migrations if needed."""
    path = db_path or os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)
    conn = get_db_connection(path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            emergency_type TEXT NOT NULL,
            language TEXT NOT NULL,
            latitude REAL,
            longitude REAL,
            location_url TEXT,
            recipient_masked TEXT NOT NULL,
            status TEXT NOT NULL,
            twilio_sid TEXT,
            error_message TEXT
        )
    """)
    conn.commit()
    conn.close()

def log_incident(emergency_type: str, language: str, latitude=None, longitude=None,
                 location_url=None, recipient=None, status="SUCCESS",
                 twilio_sid=None, error_message=None, db_path: str = None) -> int:
    """
    Persist an incident report with privacy protections.
    Returns the new incident ID.
    """
    path = db_path or os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)
    conn = get_db_connection(path)
    cursor = conn.cursor()
    
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%SZ")
    masked_recipient = mask_phone_number(recipient) if recipient else "Not provided"

    # Ensure latitude and longitude are valid floats or None
    lat_val = float(latitude) if latitude is not None and str(latitude).strip() != "" else None
    lon_val = float(longitude) if longitude is not None and str(longitude).strip() != "" else None

    cursor.execute("""
        INSERT INTO incidents (
            timestamp, emergency_type, language, latitude, longitude,
            location_url, recipient_masked, status, twilio_sid, error_message
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        timestamp,
        emergency_type or "Unknown Emergency",
        language or "en",
        lat_val,
        lon_val,
        location_url or "Location unavailable",
        masked_recipient,
        status,
        twilio_sid,
        error_message
    ))
    incident_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return incident_id

def get_incidents(limit: int = 50, db_path: str = None):
    """Retrieve recent incidents list."""
    path = db_path or os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)
    conn = get_db_connection(path)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM incidents
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))
    rows = cursor.fetchall()
    incidents = [dict(row) for row in rows]
    conn.close()
    return incidents
