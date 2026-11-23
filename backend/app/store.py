"""Számlák és feltöltések tárolása, duplikáció-szűrés."""
from __future__ import annotations

import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.aggregate import InvoiceFacts, name_key
from app.extraction.extractor import Extraction


def invoice_no_key(no: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", no.upper())


@dataclass
class RateInfo:
    rate: Decimal
    unit: int
    day: date
    huf_total: int


def find_duplicate(conn: sqlite3.Connection, ex: Extraction) -> int | None:
    """Azonos számlaszám és azonos kiállító (közös adóazonosító vagy azonos név) = ugyanaz a számla."""
    rows = conn.execute(
        "SELECT id, seller_name, seller_tax_ids FROM invoices WHERE invoice_no_key=?", (invoice_no_key(ex.invoice_no),)
    ).fetchall()
    for r in rows:
        ids = set(json.loads(r["seller_tax_ids"]))
        if ids & set(ex.seller.tax_ids):
            return r["id"]
        if not ids and not ex.seller.tax_ids and r["seller_name"] and ex.seller.name and name_key(r["seller_name"]) == name_key(ex.seller.name):
            return r["id"]
    return None


def insert_invoice(conn: sqlite3.Connection, ex: Extraction, rate: RateInfo | None, sha256: str, filename: str, method: str = "szabaly") -> int:
    p = ex.partner
    cur = conn.execute(
        """INSERT INTO invoices (invoice_no, invoice_no_key, direction, seller_name, seller_tax_ids, buyer_name, buyer_tax_ids,
           partner_name, partner_tax_ids, issue_date, supply_date, due_date, currency, gross_total, net_total, vat_total,
           rate, rate_unit, rate_day, huf_total, warnings, method, source_sha256, source_filename)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            ex.invoice_no, invoice_no_key(ex.invoice_no), ex.direction, ex.seller.name, json.dumps(ex.seller.tax_ids),
            ex.buyer.name, json.dumps(ex.buyer.tax_ids), p.name, json.dumps(p.tax_ids), ex.issue_date.isoformat(),
            ex.supply_date.isoformat(), ex.due_date.isoformat(), ex.currency, str(ex.gross_total),
            None if ex.net_total is None else str(ex.net_total), None if ex.vat_total is None else str(ex.vat_total),
            None if rate is None else str(rate.rate), None if rate is None else rate.unit,
            None if rate is None else rate.day.isoformat(), None if rate is None else rate.huf_total,
            json.dumps(ex.warnings, ensure_ascii=False), method, sha256, filename,
        ),
    )
    return cur.lastrowid


RATE_PENDING_PREFIX = "Árfolyam nem érhető el"


def set_rate(conn: sqlite3.Connection, invoice_id: int, rate: RateInfo) -> None:
    row = conn.execute("SELECT warnings FROM invoices WHERE id=?", (invoice_id,)).fetchone()
    warnings = [w for w in json.loads(row["warnings"]) if not w.startswith(RATE_PENDING_PREFIX)]
    conn.execute(
        "UPDATE invoices SET rate=?, rate_unit=?, rate_day=?, huf_total=?, warnings=? WHERE id=?",
        (str(rate.rate), rate.unit, rate.day.isoformat(), rate.huf_total, json.dumps(warnings, ensure_ascii=False), invoice_id),
    )


def log_upload(conn: sqlite3.Connection, filename: str, sha256: str, status: str, message: str | None, invoice_id: int | None) -> int:
    return conn.execute(
        "INSERT INTO uploads (filename, sha256, status, message, invoice_id) VALUES (?, ?, ?, ?, ?)",
        (filename, sha256, status, message, invoice_id),
    ).lastrowid


def invoice_for_sha(conn: sqlite3.Connection, sha256: str) -> int | None:
    r = conn.execute("SELECT id FROM invoices WHERE source_sha256=? LIMIT 1", (sha256,)).fetchone()
    return r["id"] if r else None


def all_invoices(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM invoices ORDER BY due_date, invoice_no").fetchall()


SEARCH_COLUMNS = ("invoice_no", "partner_name", "seller_name", "buyer_name", "source_filename")


@dataclass
class InvoicePage:
    rows: list[sqlite3.Row]
    total: int
    page: int
    pages: int


# Rendezési kulcs -> SQL-kifejezés; csak ezek kerülhetnek a lekérdezésbe.
SORT_COLUMNS = {
    "invoice_no": "invoice_no_key",
    "seller": "ulower(seller_name)",
    "buyer": "ulower(buyer_name)",
    "issue_date": "issue_date",
    "supply_date": "supply_date",
    "due_date": "due_date",
    "huf_total": "huf_total",
}


@dataclass(frozen=True)
class InvoiceFilter:
    q: str = ""
    direction: str | None = None
    month: str | None = None
    currency: str | None = None
    flagged: bool = False
    sort: str = "due_date"
    order: str = "asc"


def search_invoices(conn: sqlite3.Connection, f: InvoiceFilter = InvoiceFilter(), page: int = 1, page_size: int = 25) -> InvoicePage:
    """Szűrt, rendezett, lapozott számlalista; a túl nagy oldalszám az utolsó oldalra esik."""
    where, args = [], []
    if f.direction:
        where.append("direction = ?")
        args.append(f.direction)
    if f.month:
        where.append("substr(due_date, 1, 7) = ?")
        args.append(f.month)
    if f.currency:
        where.append("currency = ?")
        args.append(f.currency)
    if f.flagged:
        where.append("(warnings <> '[]' OR huf_total IS NULL)")
    if f.q.strip():
        pattern = "%" + re.sub(r"([\\%_])", r"\\\1", f.q.strip().casefold()) + "%"
        where.append("(" + " OR ".join(f"ulower(IFNULL({c}, '')) LIKE ? ESCAPE '\\'" for c in SEARCH_COLUMNS) + ")")
        args += [pattern] * len(SEARCH_COLUMNS)
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    col = SORT_COLUMNS[f.sort]
    order = "DESC" if f.order == "desc" else "ASC"
    total = conn.execute(f"SELECT COUNT(*) FROM invoices {clause}", args).fetchone()[0]
    pages = max(1, -(-total // page_size))
    page = min(max(1, page), pages)
    rows = conn.execute(
        f"SELECT * FROM invoices {clause} ORDER BY {col} IS NULL, {col} {order}, due_date, invoice_no_key, id LIMIT ? OFFSET ?",
        [*args, page_size, (page - 1) * page_size],
    ).fetchall()
    return InvoicePage(rows, total, page, pages)


def currencies(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT DISTINCT currency FROM invoices ORDER BY currency")]


def failed_uploads(conn: sqlite3.Connection, limit: int = 50) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT filename, status, message, created_at FROM uploads WHERE status = 'hiba' ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


def facts(rows: list[sqlite3.Row]) -> list[InvoiceFacts]:
    """Csak a forintra átváltott számlák kerülnek az összesítésbe."""
    return [
        InvoiceFacts(r["direction"], date.fromisoformat(r["due_date"]), r["huf_total"], r["partner_name"], tuple(json.loads(r["partner_tax_ids"])))
        for r in rows if r["huf_total"] is not None
    ]
