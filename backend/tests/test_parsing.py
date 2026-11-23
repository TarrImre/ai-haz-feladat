from datetime import date
from decimal import Decimal

import pytest

from app.extraction.parsing import detect_currency, parse_amount, parse_date
from app.extraction.taxid import find_tax_ids
from app.extraction.vocab import match_field


@pytest.mark.parametrize("text,expected", [
    ("2026.03.15.", date(2026, 3, 15)),
    ("2026-03-15", date(2026, 3, 15)),
    ("15.03.2026", date(2026, 3, 15)),
    ("15/03/2026", date(2026, 3, 15)),
    ("03/25/2026", date(2026, 3, 25)),
    ("15 mars 2026", date(2026, 3, 15)),
    ("15. März 2026", date(2026, 3, 15)),
    ("March 15, 2026", date(2026, 3, 15)),
    ("15 March 2026", date(2026, 3, 15)),
    ("2026. március 15.", date(2026, 3, 15)),
    ("15 de marzo de 2026", date(2026, 3, 15)),
    ("15 marzo 2026", date(2026, 3, 15)),
    ("15 marca 2026", date(2026, 3, 15)),
    ("28 décembre 2026", date(2026, 12, 28)),
    ("14 dni", None),
    ("", None),
    ("2026.02.30.", None),
])
def test_parse_date(text, expected):
    assert parse_date(text) == expected


@pytest.mark.parametrize("text,value,cur", [
    ("1 234,56", "1234.56", None),
    ("1.234,56 €", "1234.56", "EUR"),
    ("1,234.56", "1234.56", None),
    ("€5,452.00", "5452.00", "EUR"),
    ("$739.00", "739.00", "USD"),
    ("£11,805.00", "11805.00", "GBP"),
    ("121 158 HUF", "121158", "HUF"),
    ("424 688 Ft", "424688", "HUF"),
    ("4 548,00 PLN", "4548.00", "PLN"),
    ("2.744,00 €", "2744.00", "EUR"),
    ("12 798 679", "12798679", None),
    ("1.234", "1234", None),
    ("0,00 €", "0.00", "EUR"),
])
def test_parse_amount(text, value, cur):
    assert parse_amount(text) == (Decimal(value), cur)


def test_parse_amount_rejects_percent_and_dates():
    assert parse_amount("27%") is None
    assert parse_amount("2026.03.15.") is None


def test_detect_currency_word_boundaries():
    assert detect_currency("Fizetendő: 100 Ft") == "HUF"
    assert detect_currency("Software") is None


def test_tax_ids_normalized():
    assert find_tax_ids("Adószám: 14829375-2-43 Közösségi adószám: HU14829375") == ["HU14829375"]
    assert find_tax_ids("USt-IdNr.: ATU58392716") == ["ATU58392716"]
    assert find_tax_ids("NIP: 527-284-61-93") == ["PL5272846193"]
    assert find_tax_ids("EIN 84-3920175") == ["EIN843920175"]
    assert find_tax_ids("VAT No. GB 284 7193 56") == ["GB284719356"]


@pytest.mark.parametrize("label,field", [
    ("Fizetési határidő / Due date", "due_date"),
    ("Teljesítés dátuma:", "supply_date"),
    ("ÁFA összesen (27%)", "vat"),
    ("Base imponible total", "net"),
    ("TOTALE DOCUMENTO", "total"),
    ("Termin płatności", "due_date"),
    ("Az ÁFA összege forintban", None),
    ("Nettó egységár", None),
])
def test_label_vocabulary(label, field):
    assert match_field(label) == field
