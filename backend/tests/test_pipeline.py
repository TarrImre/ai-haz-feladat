"""Feldolgozási folyamat: duplikáció, hibás fájl, árfolyam-hiány és pótlás."""
from datetime import date

import httpx
import pytest

from app import db, store
from app.mnb import MnbClient, RateService
from app.pipeline import process_files, retry_missing_rates
from tests.fake_mnb import QUOTES, FakeMnb
from tests.samples import SAMPLES_DIR
from tests.synth import make_pdf

SAMPLE = SAMPLES_DIR / "056_NW-2026-0014.pdf"


def invoice_pdf(no: str, supply: str = "2026.03.09.", y_shift: float = 0) -> bytes:
    y = lambda v: v + y_shift  # noqa: E731
    return make_pdf([[
        (40, y(40), "Nordwind Solutions Kft.", True), (40, y(52), "Adószám: 26481937-2-43"),
        (40, y(90), "Vevő:", True), (40, y(102), "Példa Partner Zrt."), (40, y(114), "Adószám: 87654321-2-42"),
        (350, y(90), "Számlaszám:"), (450, y(90), no),
        (350, y(102), "Kiállítás dátuma:"), (450, y(102), "2026.03.10."),
        (350, y(114), "Teljesítés dátuma:"), (450, y(114), supply),
        (350, y(126), "Fizetési határidő:"), (450, y(126), "2026.04.09."),
        (350, y(138), "Pénznem:"), (450, y(138), "EUR"),
        (300, y(260), "Nettó összesen"), (470, y(260), "1 000,00 EUR"),
        (300, y(272), "ÁFA összesen (27%)"), (470, y(272), "270,00 EUR"),
        (300, y(284), "Fizetendő összesen", True), (470, y(284), "1 270,00 EUR", True),
    ]])


@pytest.fixture
def env():
    fake = FakeMnb(QUOTES)
    conn = db.connect(":memory:")
    service = RateService(conn, MnbClient("http://mnb.test", transport=httpx.MockTransport(fake)), today=date(2026, 11, 23))
    return conn, service, fake


def test_valid_invoice_is_stored_with_huf(env):
    conn, service, _ = env
    [r] = process_files(conn, service, [("a.pdf", invoice_pdf("NW-1"))])
    assert r.status == "ok"
    row = store.all_invoices(conn)[0]
    assert (row["direction"], row["partner_name"], row["rate"], row["rate_day"], row["huf_total"]) == (
        "kimeno", "Példa Partner Zrt.", "396.92", "2026-03-09", 504088)


def test_same_file_twice_is_not_duplicated(env):
    conn, service, _ = env
    data = invoice_pdf("NW-1")
    process_files(conn, service, [("a.pdf", data)])
    [r] = process_files(conn, service, [("a-copy.pdf", data)])
    assert r.status == "duplikalt"
    assert len(store.all_invoices(conn)) == 1


def test_same_invoice_different_bytes_is_duplicate_by_seller_and_number(env):
    conn, service, _ = env
    process_files(conn, service, [("a.pdf", invoice_pdf("NW-2026/0001"))])
    [r] = process_files(conn, service, [("scan.pdf", invoice_pdf("NW-2026-0001", y_shift=5))])
    assert r.status == "duplikalt"
    assert len(store.all_invoices(conn)) == 1


def test_same_number_from_other_seller_is_not_duplicate(env):
    conn, service, _ = env
    process_files(conn, service, [("a.pdf", invoice_pdf("NW-1"))])
    data = make_pdf([[
        (40, 40, "Másik Kft.", True), (40, 52, "Adószám: 99999999-2-41"),
        (40, 90, "Vevő:", True), (40, 102, "Nordwind Solutions Kft."), (40, 114, "Adószám: 26481937-2-43"),
        (350, 90, "Számlaszám:"), (450, 90, "NW-1"),
        (350, 102, "Kiállítás dátuma:"), (450, 102, "2026.03.10."),
        (350, 114, "Teljesítés dátuma:"), (450, 114, "2026.03.09."),
        (350, 126, "Fizetési határidő:"), (450, 126, "2026.04.09."),
        (300, 284, "Fizetendő összesen", True), (470, 284, "1 000 Ft", True),
    ]])
    [r] = process_files(conn, service, [("b.pdf", data)])
    assert r.status in ("ok", "figyelmeztetes")
    assert len(store.all_invoices(conn)) == 2


def test_bad_file_does_not_stop_batch(env):
    conn, service, _ = env
    results = process_files(conn, service, [("bad.pdf", b"garbage"), ("good.pdf", invoice_pdf("NW-1")), ("empty.pdf", make_pdf([[]]))])
    assert [r.status for r in results] == ["hiba", "ok", "hiba"]
    assert len(store.all_invoices(conn)) == 1
    logged = conn.execute("SELECT filename, status FROM uploads ORDER BY id").fetchall()
    assert [(r["filename"], r["status"]) for r in logged] == [("bad.pdf", "hiba"), ("good.pdf", "ok"), ("empty.pdf", "hiba")]


def test_batch_needs_single_mnb_call(env):
    conn, service, fake = env
    process_files(conn, service, [(f"{i}.pdf", invoice_pdf(f"NW-{i}", supply=f"2026.03.0{6 + i % 4}.")) for i in range(8)])
    assert len(fake.requests) == 1


def test_mnb_down_stores_invoice_and_retry_fills_rate(env):
    conn, _, fake = env
    def down(request):
        raise httpx.ConnectError("down")
    broken = RateService(conn, MnbClient("http://mnb.test", transport=httpx.MockTransport(down)), today=date(2026, 11, 23))
    [r] = process_files(conn, broken, [("a.pdf", invoice_pdf("NW-1"))])
    assert r.status == "figyelmeztetes" and "Árfolyam" in r.message
    assert store.all_invoices(conn)[0]["huf_total"] is None
    assert store.facts(store.all_invoices(conn)) == []

    working = RateService(conn, MnbClient("http://mnb.test", transport=httpx.MockTransport(fake)), today=date(2026, 11, 23))
    assert retry_missing_rates(conn, working) == 1
    row = store.all_invoices(conn)[0]
    assert row["huf_total"] == 504088 and row["warnings"] == "[]"


def test_real_sample_end_to_end(env):
    conn, service, _ = env
    [r] = process_files(conn, service, [("x.pdf", SAMPLE.read_bytes())])
    row = store.all_invoices(conn)[0]
    assert r.status == "ok"
    assert (row["invoice_no"], row["currency"], row["gross_total"], row["rate"], row["huf_total"]) == (
        "NW-2026-0014", "EUR", "1153.16", "396.92", 457712)
