"""Számlalista: szerveroldali keresés, szűrés, rendezés és lapozás."""
import pytest

from app import db, store
from app.store import InvoiceFilter as F


def add(conn, no, direction="kimeno", partner="Példa Partner Zrt.", due="2026-03-01", filename=None,
        currency="HUF", huf=100, warnings="[]", issue=None):
    seller, buyer = ("Nordwind Solutions Kft.", partner) if direction == "kimeno" else (partner, "Nordwind Solutions Kft.")
    conn.execute(
        """INSERT INTO invoices (invoice_no, invoice_no_key, direction, seller_name, seller_tax_ids, buyer_name, buyer_tax_ids,
           partner_name, partner_tax_ids, issue_date, supply_date, due_date, currency, gross_total, huf_total, warnings,
           source_sha256, source_filename)
           VALUES (?, ?, ?, ?, '[]', ?, '[]', ?, '[]', ?, ?, ?, ?, '100', ?, ?, ?, ?)""",
        (no, store.invoice_no_key(no), direction, seller, buyer, partner, issue or due, due, due, currency, huf, warnings,
         no, filename or f"{no}.pdf"),
    )


@pytest.fixture
def conn():
    c = db.connect(":memory:")
    for n in range(1, 61):
        add(c, f"NW-{n:03d}", direction="kimeno" if n % 3 else "bejovo", due=f"2026-{(n - 1) // 10 + 1:02d}-{(n - 1) % 10 + 1:02d}", huf=n * 1000)
    add(c, "KT-1", "bejovo", "Kovács és Társa Könyvelőiroda Bt.", "2026-12-01", currency="EUR", huf=5)
    add(c, "OR-1", "bejovo", "ŐRÜLT ÁRAK KFT.", "2026-12-02", currency="EUR", huf=None, warnings='["Árfolyam nem érhető el"]')
    add(c, "PCT-1", "kimeno", "Száz százalék Kft.", "2026-12-03", filename="szamla_100%_kesz.pdf", warnings='["Nettó + ÁFA eltér"]', huf=999999)
    return c


def numbers(page):
    return [r["invoice_no"] for r in page.rows]


def search(conn, page=1, page_size=25, **kw):
    return store.search_invoices(conn, F(**kw), page, page_size)


def test_pages_split_and_total(conn):
    first = search(conn)
    last = search(conn, page=3)
    assert (first.total, first.pages, len(first.rows)) == (63, 3, 25)
    assert numbers(first)[:2] == ["NW-001", "NW-002"]
    assert len(last.rows) == 13 and numbers(last)[-1] == "PCT-1"


def test_page_beyond_last_falls_back_to_last(conn):
    res = search(conn, page=99)
    assert (res.page, numbers(res)[-1]) == (3, "PCT-1")


def test_empty_result_is_one_empty_page(conn):
    res = search(conn, q="nincs ilyen", page=5)
    assert (res.total, res.page, res.pages, res.rows) == (0, 1, 1, [])


def test_search_is_case_insensitive_with_accents(conn):
    assert numbers(search(conn, q="őrült")) == ["OR-1"]
    assert numbers(search(conn, q="KÖNYVELŐ")) == ["KT-1"]
    assert numbers(search(conn, q="nw-06")) == ["NW-060"]


def test_search_matches_seller_buyer_and_filename(conn):
    assert search(conn, q="nordwind").total == 63
    assert numbers(search(conn, q="kt-1.pdf")) == ["KT-1"]


def test_like_wildcards_are_literal(conn):
    assert numbers(search(conn, q="100%")) == ["PCT-1"]
    assert search(conn, q="%").total == 1
    assert search(conn, q="_").total == 1


def test_direction_filter_combines_with_search(conn):
    assert search(conn, direction="bejovo").total == 22
    assert numbers(search(conn, q="nw-00", direction="bejovo")) == ["NW-003", "NW-006", "NW-009"]


def test_month_filter_uses_due_date(conn):
    assert numbers(search(conn, month="2026-12")) == ["KT-1", "OR-1", "PCT-1"]
    assert search(conn, month="2026-02").total == 10
    assert search(conn, month="2026-07").total == 0


def test_currency_filter(conn):
    assert numbers(search(conn, currency="EUR")) == ["KT-1", "OR-1"]


def test_flagged_means_warning_or_missing_rate(conn):
    assert numbers(search(conn, flagged=True)) == ["OR-1", "PCT-1"]


def test_sort_by_huf_desc_keeps_missing_last(conn):
    res = search(conn, sort="huf_total", order="desc", page_size=100)
    assert numbers(res)[:2] == ["PCT-1", "NW-060"]
    assert numbers(res)[-2:] == ["KT-1", "OR-1"]


def test_sort_by_seller_ignores_case_accented_letters_after_z(conn):
    assert numbers(search(conn, sort="seller", month="2026-12")) == ["KT-1", "PCT-1", "OR-1"]
    assert numbers(search(conn, sort="buyer", order="desc", month="2026-12")) == ["PCT-1", "KT-1", "OR-1"]


def test_sort_desc_and_paging_together(conn):
    res = search(conn, sort="invoice_no", order="desc", page=1, page_size=3)
    assert numbers(res) == ["PCT-1", "OR-1", "NW-060"]
