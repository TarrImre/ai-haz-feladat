"""Összesítés: havi sor üres hónapokkal, partner-összevonás adószám és név alapján."""
from datetime import date

from app.aggregate import InvoiceFacts, monthly, partners


def inv(direction, due, huf, name, *ids):
    return InvoiceFacts(direction, due, huf, name, tuple(ids))


def test_monthly_continuous_with_zero_months():
    rows = monthly([
        inv("bejovo", date(2026, 1, 31), 100, "A"),
        inv("kimeno", date(2026, 1, 1), 50, "B"),
        inv("bejovo", date(2026, 4, 2), 30, "A"),
        inv("kimeno", date(2026, 4, 30), 20, "B"),
    ])
    assert [(r.month, r.incoming, r.outgoing) for r in rows] == [
        ("2026-01", 100, 50), ("2026-02", 0, 0), ("2026-03", 0, 0), ("2026-04", 30, 20),
    ]


def test_monthly_crosses_year_boundary():
    rows = monthly([inv("bejovo", date(2025, 11, 5), 1, "A"), inv("kimeno", date(2026, 2, 5), 2, "A")])
    assert [r.month for r in rows] == ["2025-11", "2025-12", "2026-01", "2026-02"]


def test_monthly_empty():
    assert monthly([]) == []


def test_partner_merged_by_tax_id_despite_name_variants():
    cols = partners([
        inv("bejovo", date(2026, 1, 1), 100, "DUNA LOGISZTIKA ZRT.", "HU14829375"),
        inv("kimeno", date(2026, 2, 1), 300, "Duna Logisztika Zrt.", "HU14829375"),
        inv("kimeno", date(2026, 3, 1), 5, "Duna Logisztika Zrt.", "HU14829375"),
    ])
    assert len(cols) == 1
    c = cols[0]
    assert (c.name, c.incoming, c.outgoing) == ("Duna Logisztika Zrt.", 100, 305)


def test_partner_ids_chain_across_invoices():
    cols = partners([
        inv("bejovo", date(2026, 1, 1), 1, "Lumière Conseil SARL", "FR47829461375"),
        inv("kimeno", date(2026, 1, 1), 2, "LUMIÈRE CONSEIL SARL", "FR47829461375", "82946137500024"),
        inv("kimeno", date(2026, 1, 1), 4, "Lumiere Conseil", "82946137500024"),
    ])
    assert len(cols) == 1 and cols[0].outgoing == 6 and cols[0].incoming == 1


def test_partner_without_tax_id_merged_by_normalized_name():
    cols = partners([
        inv("bejovo", date(2026, 1, 1), 1, "Atlas Cloud Inc."),
        inv("bejovo", date(2026, 1, 1), 2, "ATLAS CLOUD INC"),
    ])
    assert len(cols) == 1 and cols[0].incoming == 3


def test_distinct_partners_stay_separate_and_zero_direction_is_zero():
    cols = partners([
        inv("bejovo", date(2026, 1, 1), 10, "Alpha Kft.", "HU11111111"),
        inv("kimeno", date(2026, 1, 1), 20, "Beta Kft.", "HU22222222"),
    ])
    by_name = {c.name: c for c in cols}
    assert (by_name["Alpha Kft."].incoming, by_name["Alpha Kft."].outgoing) == (10, 0)
    assert (by_name["Beta Kft."].incoming, by_name["Beta Kft."].outgoing) == (0, 20)
