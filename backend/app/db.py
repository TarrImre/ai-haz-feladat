"""SQLite-kapcsolat és séma."""
from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS mnb_rates (
    day TEXT NOT NULL,
    currency TEXT NOT NULL,
    rate TEXT NOT NULL,
    unit INTEGER NOT NULL,
    PRIMARY KEY (day, currency)
);
CREATE TABLE IF NOT EXISTS mnb_coverage (
    currency TEXT NOT NULL,
    start_day TEXT NOT NULL,
    end_day TEXT NOT NULL,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_mnb_coverage ON mnb_coverage (currency, start_day, end_day);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY,
    invoice_no TEXT NOT NULL,
    invoice_no_key TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('bejovo', 'kimeno')),
    seller_name TEXT,
    seller_tax_ids TEXT NOT NULL,
    buyer_name TEXT,
    buyer_tax_ids TEXT NOT NULL,
    partner_name TEXT NOT NULL,
    partner_tax_ids TEXT NOT NULL,
    issue_date TEXT NOT NULL,
    supply_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    currency TEXT NOT NULL,
    gross_total TEXT NOT NULL,
    net_total TEXT,
    vat_total TEXT,
    rate TEXT,
    rate_unit INTEGER,
    rate_day TEXT,
    huf_total INTEGER,
    warnings TEXT NOT NULL DEFAULT '[]',
    method TEXT NOT NULL DEFAULT 'szabaly',
    source_sha256 TEXT NOT NULL,
    source_filename TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_invoices_no ON invoices (invoice_no_key);

CREATE TABLE IF NOT EXISTS uploads (
    id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('ok', 'figyelmeztetes', 'duplikalt', 'hiba')),
    message TEXT,
    invoice_id INTEGER REFERENCES invoices (id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS ix_uploads_sha ON uploads (sha256);
"""


def connect(path: Path | str) -> sqlite3.Connection:
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    # Az SQLite LOWER() csak ASCII-t kisbetűsít, az ő/Ő-t nem.
    conn.create_function("ulower", 1, lambda s: s.casefold() if isinstance(s, str) else s, deterministic=True)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA)
    return conn
