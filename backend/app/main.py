"""FastAPI-backend: feltöltés, kimutatás, számlalista (a felület a Next.js-frontend)."""
from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Query, UploadFile

from app import aggregate, config, db, store
from app.responses import install_error_handlers, success
from app.mnb import MnbClient, RateService
from app.pipeline import process_files, retry_missing_rates

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_FILES_PER_REQUEST = 200

app = FastAPI(title="Számlafeldolgozó")
install_error_handlers(app)

_conn = db.connect(config.DB_PATH)
_service = RateService(_conn, MnbClient(config.MNB_ENDPOINT))
# Egy SQLite-kapcsolat, minden hozzáférés zár alatt.
_lock = threading.Lock()


@app.get("/api/health")
def health() -> dict:
    return success({"ok": True})


@app.post("/api/upload")
def upload(files: list[UploadFile] = File(...)) -> dict:
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(413, f"Egy kérésben legfeljebb {MAX_FILES_PER_REQUEST} fájl")
    batch, early = [], []
    for f in files:
        name = Path(f.filename or "névtelen.pdf").name
        data = f.file.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            early.append({"filename": name, "status": "hiba", "message": "A fájl nagyobb 20 MB-nál"})
        else:
            batch.append((name, data))
    with _lock:
        results = process_files(_conn, _service, batch)
    return success({"results": early + [asdict(r) for r in results]})


def _invoice_json(r) -> dict:
    return {
        "id": r["id"], "invoice_no": r["invoice_no"], "direction": r["direction"],
        "seller_name": r["seller_name"], "seller_tax_ids": json.loads(r["seller_tax_ids"]),
        "buyer_name": r["buyer_name"], "buyer_tax_ids": json.loads(r["buyer_tax_ids"]),
        "partner_name": r["partner_name"], "issue_date": r["issue_date"], "supply_date": r["supply_date"],
        "due_date": r["due_date"], "currency": r["currency"], "gross_total": r["gross_total"],
        "net_total": r["net_total"], "vat_total": r["vat_total"], "rate": r["rate"], "rate_unit": r["rate_unit"],
        "rate_day": r["rate_day"], "huf_total": r["huf_total"], "warnings": json.loads(r["warnings"]),
        "method": r["method"], "source_filename": r["source_filename"],
    }


@app.get("/api/report")
def report() -> dict:
    with _lock:
        rows = store.all_invoices(_conn)
        currencies = store.currencies(_conn)
        uploads = store.failed_uploads(_conn)
    facts = store.facts(rows)
    return success({
        "company": {"name": config.OUR_COMPANY_NAME, "tax_id": config.OUR_TAX_IDS[0]},
        "months": [asdict(m) for m in aggregate.monthly(facts)],
        "partners": [asdict(p) for p in aggregate.partners(facts)],
        "invoice_count": len(rows),
        "currencies": currencies,
        "pending_rates": sum(1 for r in rows if r["huf_total"] is None),
        "failed_uploads": [dict(u) for u in uploads],
    })


@app.get("/api/invoices")
def invoices(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    q: str = Query("", max_length=200),
    direction: Literal["bejovo", "kimeno"] | None = None,
    month: str | None = Query(None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    currency: str | None = Query(None, pattern=r"^[A-Z]{3}$"),
    flagged: bool = False,
    sort: Literal["invoice_no", "seller", "buyer", "issue_date", "supply_date", "due_date", "huf_total"] = "due_date",
    order: Literal["asc", "desc"] = "asc",
) -> dict:
    f = store.InvoiceFilter(q, direction, month, currency, flagged, sort, order)
    with _lock:
        res = store.search_invoices(_conn, f, page, page_size)
    return success({"items": [_invoice_json(r) for r in res.rows], "total": res.total, "page": res.page, "pages": res.pages, "page_size": page_size})


@app.post("/api/retry-rates")
def retry_rates() -> dict:
    with _lock:
        n = retry_missing_rates(_conn, _service)
    return success({"updated": n}, f"{n} számla árfolyama pótolva.")


@app.delete("/api/data")
def reset_data() -> dict:
    """Számlák és feltöltési napló törlése; a tárolt MNB-árfolyamok megmaradnak."""
    with _lock, _conn:
        _conn.execute("DELETE FROM uploads")
        n = _conn.execute("DELETE FROM invoices").rowcount
    return success({"deleted": n}, f"{n} számla törölve.")
