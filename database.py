
import sqlite3
import os
from datetime import datetime

DB_PATH = os.environ.get(
    "DB_PATH",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "aarogya.db")
)


def get_db():
    """Open a new database connection with row_factory for dict-like access."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # rows accessible as dicts
    conn.execute("PRAGMA foreign_keys = ON")  # enforce FK constraints
    return conn


def init_db():
    """
    Create all tables if they don't exist.
    Called once at application startup.
    """
    conn = get_db()
    cur = conn.cursor()

    # ── Users table ──────────────────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name     TEXT    NOT NULL,
            email         TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            role          TEXT    NOT NULL CHECK(role IN ('patient','doctor','admin')),
            specialization TEXT,           -- for doctors
            hospital_name  TEXT,           -- for doctors/admins
            phone          TEXT,
            created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
            is_active     INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Medical Records (immutable; doctor/patient cannot edit) ─
    cur.execute("""
        CREATE TABLE IF NOT EXISTS medical_records (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id      INTEGER NOT NULL REFERENCES users(id),
            symptoms        TEXT    NOT NULL,   -- JSON list of symptom names
            predicted_disease TEXT  NOT NULL,
            confidence      REAL    NOT NULL,
            ai_description  TEXT,
            ai_precautions  TEXT,               -- JSON list
            differentials   TEXT,               -- JSON list of {disease, probability}
            blockchain_hash TEXT    NOT NULL,   -- SHA-256 of this record
            prev_hash       TEXT    NOT NULL,   -- links to previous record's hash
            timestamp       TEXT    NOT NULL DEFAULT (datetime('now')),
            is_verified     INTEGER NOT NULL DEFAULT 1
        )
    """)

    # ── Doctor Diagnoses (additive only; original record unchanged) ─
    cur.execute("""
        CREATE TABLE IF NOT EXISTS diagnoses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            record_id   INTEGER NOT NULL REFERENCES medical_records(id),
            doctor_id   INTEGER NOT NULL REFERENCES users(id),
            notes       TEXT    NOT NULL,
            prescription TEXT,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── Consent Management ───────────────────────────────────
    # Patient explicitly grants a doctor access to their records.
    cur.execute("""
        CREATE TABLE IF NOT EXISTS consents (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id  INTEGER NOT NULL REFERENCES users(id),
            doctor_id   INTEGER NOT NULL REFERENCES users(id),
            granted     INTEGER NOT NULL DEFAULT 1,  -- 1=granted, 0=revoked
            granted_at  TEXT    NOT NULL DEFAULT (datetime('now')),
            UNIQUE(patient_id, doctor_id)
        )
    """)

    # ── Patient Health Profiles ──────────────────────────────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS patient_profiles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER NOT NULL UNIQUE REFERENCES users(id),
            age             INTEGER,
            gender          TEXT,
            weight_kg       REAL,
            height_cm       REAL,
            blood_group     TEXT,
            allergies       TEXT,
            chronic_conditions TEXT,
            emergency_contact TEXT,
            updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # ── Audit Logs (append-only activity log for admin) ──────
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER REFERENCES users(id),
            action     TEXT    NOT NULL,
            details    TEXT,
            ip_address TEXT,
            timestamp  TEXT    NOT NULL DEFAULT (datetime('now'))
        )
    """)

    conn.commit()
    conn.close()
    _seed_default_admin()


def _seed_default_admin():
    """
    Creates default admin/doctor accounts for first-run testing.
    Passwords are hashed — see auth.py.
    """
    from werkzeug.security import generate_password_hash
    conn = get_db()
    cur = conn.cursor()

    # Check if admin already exists
    if cur.execute("SELECT id FROM users WHERE email='admin@aarogya.ai'").fetchone():
        conn.close()
        return

    admin_hash  = generate_password_hash("Admin@123")
    doctor_hash = generate_password_hash("Doctor@123")

    cur.execute("""
        INSERT INTO users (full_name, email, password_hash, role, hospital_name)
        VALUES (?, ?, ?, ?, ?)
    """, ("System Admin", "admin@aarogya.ai", admin_hash, "admin", "Aarogya Central Hospital"))

    cur.execute("""
        INSERT INTO users (full_name, email, password_hash, role, specialization, hospital_name)
        VALUES (?, ?, ?, ?, ?, ?)
    """, ("Dr. Rajan Mehta", "doctor@aarogya.ai", doctor_hash, "doctor", "General Medicine", "Aarogya Central Hospital"))

    conn.commit()
    conn.close()
    print("[DB] Default admin and doctor seeded.")


# ── Convenience Query Helpers ────────────────────────────────

def log_action(user_id, action: str, details: str = "", ip: str = ""):
    """Append an entry to the audit log. Call after important actions."""
    conn = get_db()
    conn.execute(
        "INSERT INTO audit_logs (user_id, action, details, ip_address) VALUES (?,?,?,?)",
        (user_id, action, details, ip)
    )
    conn.commit()
    conn.close()


def get_user_by_email(email: str):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    conn.close()
    return user


def get_user_by_id(uid: int):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return user


def get_last_hash_for_patient(patient_id: int) -> str:
    """
    Returns the blockchain_hash of the patient's most recent record.
    This becomes the prev_hash for the next record — creating the chain.
    If no previous record exists, returns the genesis hash.
    """
    from blockchain.chain import build_genesis_hash
    conn = get_db()
    row = conn.execute(
        "SELECT blockchain_hash FROM medical_records WHERE patient_id=? ORDER BY id DESC LIMIT 1",
        (patient_id,)
    ).fetchone()
    conn.close()
    return row["blockchain_hash"] if row else build_genesis_hash()

def get_patient_profile(user_id: int):
    conn = get_db()
    profile = conn.execute("SELECT * FROM patient_profiles WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return profile
