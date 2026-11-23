"""Feltöltött fájlok feldolgozása: kinyerés, árfolyam, duplikáció-szűrés, tárolás."""
from __future__ import annotations

import hashlib
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app import store
from app.extraction.extractor import Extraction, extract
from app.extraction.pdf_spans import PdfReadError
from app.mnb import MnbError, RateService, to_huf

log = logging.getLogger(__name__)


@dataclass
class FileResult:
    filename: str
    status: str
    message: str | None = None
    invoice_id: int | None = None
    invoice_no: str | None = None


def _rate_info(service: RateService, ex: Extraction) -> tuple[store.RateInfo | None, str | None]:
    try:
        r = service.rate_for(ex.currency, ex.supply_date)
    except MnbError as exc:
        return None, f"{store.RATE_PENDING_PREFIX}, később újrapróbálja: {exc}"
    return store.RateInfo(r.rate, r.unit, r.day, to_huf(ex.gross_total, r)), None


def process_files(conn: sqlite3.Connection, service: RateService, files: list[tuple[str, bytes]]) -> list[FileResult]:
    results: list[FileResult | None] = [None] * len(files)
    pending: list[tuple[int, str, str, Extraction]] = []
    seen_sha: set[str] = set()
    shas: list[str] = [""] * len(files)

    for idx, (name, data) in enumerate(files):
        sha = hashlib.sha256(data).hexdigest()
        shas[idx] = sha
        existing = store.invoice_for_sha(conn, sha)
        if existing or sha in seen_sha:
            results[idx] = FileResult(name, "duplikalt", "Ez a fájl már fel lett dolgozva", existing)
            continue
        seen_sha.add(sha)
        try:
            ex = extract(data)
        except PdfReadError as exc:
            results[idx] = FileResult(name, "hiba", str(exc))
            continue
        except Exception as exc:
            log.exception("Kinyerési hiba: %s", name)
            results[idx] = FileResult(name, "hiba", f"Váratlan feldolgozási hiba: {exc}")
            continue
        if ex.errors:
            results[idx] = FileResult(name, "hiba", "; ".join(ex.errors), invoice_no=ex.invoice_no)
            continue
        pending.append((idx, name, sha, ex))

    try:
        service.prefetch([(ex.currency, ex.supply_date) for *_, ex in pending])
    except MnbError as exc:
        log.warning("MNB-előlekérés sikertelen: %s", exc)

    for idx, name, sha, ex in pending:
        with conn:
            dup = store.find_duplicate(conn, ex)
            if dup:
                results[idx] = FileResult(name, "duplikalt", f"A {ex.invoice_no} számla már szerepel", dup, ex.invoice_no)
                continue
            rate, rate_msg = _rate_info(service, ex)
            warnings = ex.warnings + ([rate_msg] if rate_msg else [])
            ex.warnings = warnings
            inv_id = store.insert_invoice(conn, ex, rate, sha, name)
            status = "figyelmeztetes" if warnings else "ok"
            results[idx] = FileResult(name, status, "; ".join(warnings) or None, inv_id, ex.invoice_no)

    with conn:
        for r, sha in zip(results, shas):
            store.log_upload(conn, r.filename, sha, r.status, r.message, r.invoice_id)
    return [r for r in results if r is not None]


def retry_missing_rates(conn: sqlite3.Connection, service: RateService) -> int:
    """A korábban árfolyam nélkül tárolt számlák pótlása; a sikeresek száma."""
    rows = conn.execute("SELECT id, currency, supply_date, gross_total FROM invoices WHERE huf_total IS NULL").fetchall()
    if not rows:
        return 0
    try:
        service.prefetch([(r["currency"], date.fromisoformat(r["supply_date"])) for r in rows])
    except MnbError:
        return 0
    done = 0
    with conn:
        for r in rows:
            try:
                rate = service.rate_for(r["currency"], date.fromisoformat(r["supply_date"]))
            except MnbError:
                continue
            store.set_rate(conn, r["id"], store.RateInfo(rate.rate, rate.unit, rate.day, to_huf(Decimal(r["gross_total"]), rate)))
            done += 1
    return done
