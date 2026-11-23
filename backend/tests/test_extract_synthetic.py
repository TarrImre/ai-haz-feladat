"""Általánosság: a mintában nem szereplő címkék, elrendezések, többoldalas és hibás fájl."""
from datetime import date
from decimal import Decimal

import pytest

from app.extraction.extractor import extract
from app.extraction.pdf_spans import PdfReadError
from tests.samples import SAMPLES_DIR
from tests.synth import make_pdf


def test_side_by_side_seller_buyer_blocks_hungarian():
    pdf = make_pdf([[
        (40, 40, "SZÁMLA", True),
        (40, 70, "Eladó:", True), (300, 70, "Vevő:", True),
        (40, 84, "Kis Pék Kft."), (300, 84, "Nordwind Solutions Kft."),
        (40, 96, "1051 Budapest, Fő utca 1."), (300, 96, "Infopark sétány 7., 1117 Budapest"),
        (40, 108, "Adószám: 12345678-2-41"), (300, 108, "Adószám: 26481937-2-43"),
        (40, 150, "Számla sorszáma: KP-2026/77"),
        (40, 162, "Számla kelte: 2026.05.10."),
        (40, 174, "Teljesítés kelte: 2026.05.08."),
        (40, 186, "Esedékesség: 2026.05.25."),
        (300, 260, "Nettó összeg:"), (450, 260, "100 000 Ft"),
        (300, 272, "ÁFA összeg:"), (450, 272, "27 000 Ft"),
        (300, 284, "Bruttó végösszeg:", True), (450, 284, "127 000 Ft", True),
    ]])
    ex = extract(pdf)
    assert ex.invoice_no == "KP-2026/77"
    assert ex.direction == "bejovo"
    assert ex.seller.name == "Kis Pék Kft."
    assert ex.seller.tax_ids == ["HU12345678"]
    assert (ex.issue_date, ex.supply_date, ex.due_date) == (date(2026, 5, 10), date(2026, 5, 8), date(2026, 5, 25))
    assert ex.gross_total == Decimal("127000") and ex.currency == "HUF"
    assert not ex.errors and not ex.warnings


def test_stacked_header_row_german_symbol_currency():
    pdf = make_pdf([[
        (40, 40, "Musterfirma GmbH", True), (40, 52, "USt-IdNr.: DE123456789"),
        (40, 90, "Rechnungsempfänger", True),
        (40, 102, "Nordwind Solutions Kft."), (40, 114, "USt-IdNr.: HU26481937"),
        (40, 160, "Rechnung Nr.", True), (160, 160, "Rechnungsdatum", True), (280, 160, "Lieferdatum", True), (400, 160, "Fällig am", True),
        (40, 172, "R-55/2026"), (160, 172, "3. Juni 2026"), (280, 172, "1. Juni 2026"), (400, 172, "17. Juni 2026"),
        (300, 300, "Nettobetrag"), (470, 300, "1.000,00 €"),
        (300, 312, "USt. 19%"), (470, 312, "190,00 €"),
        (300, 324, "Gesamtbetrag", True), (470, 324, "1.190,00 €", True),
    ]])
    ex = extract(pdf)
    assert ex.invoice_no == "R-55/2026"
    assert ex.direction == "bejovo"
    assert ex.seller.tax_ids == ["DE123456789"]
    assert (ex.issue_date, ex.supply_date, ex.due_date) == (date(2026, 6, 3), date(2026, 6, 1), date(2026, 6, 17))
    assert (ex.gross_total, ex.currency) == (Decimal("1190.00"), "EUR")
    assert not ex.errors and not ex.warnings


def test_outgoing_two_pages_total_on_second_page():
    page1 = [
        (40, 40, "Nordwind Solutions Kft.", True), (40, 52, "VAT No.: HU26481937"),
        (40, 90, "Customer:", True), (40, 102, "Acme Trading Ltd."), (40, 114, "VAT No.: GB 123 4567 89"),
        (350, 90, "Invoice number:"), (450, 90, "NW-2026-0901"),
        (350, 102, "Issue date:"), (450, 102, "April 2, 2026"),
        (350, 114, "Delivery date:"), (450, 114, "March 31, 2026"),
        (350, 126, "Payment due:"), (450, 126, "May 2, 2026"),
        (350, 138, "Currency:"), (450, 138, "GBP"),
    ] + [(40, 200 + i * 12, f"Item {i}   1 pc   10.00") for i in range(40)]
    page2 = [
        (300, 60, "Subtotal"), (470, 60, "£400.00"),
        (300, 72, "VAT (0%)"), (470, 72, "£0.00"),
        (300, 84, "Balance due", True), (470, 84, "£400.00", True),
    ]
    ex = extract(make_pdf([page1, page2]))
    assert ex.direction == "kimeno"
    assert ex.buyer.name == "Acme Trading Ltd." and ex.partner.tax_ids == ["GB123456789"]
    assert (ex.issue_date, ex.supply_date, ex.due_date) == (date(2026, 4, 2), date(2026, 3, 31), date(2026, 5, 2))
    assert (ex.gross_total, ex.currency) == (Decimal("400.00"), "GBP")
    assert not ex.errors


def test_foreign_currency_vat_in_huf_is_not_total():
    pdf = make_pdf([[
        (40, 40, "Nordwind Solutions Kft.", True), (40, 52, "Adószám: 26481937-2-43"),
        (40, 90, "Vevő:", True), (40, 102, "Példa Partner Zrt."), (40, 114, "Adószám: 87654321-2-42"),
        (350, 90, "Számlaszám:"), (450, 90, "NW-2026-0902"),
        (350, 102, "Kiállítás dátuma:"), (450, 102, "2026.03.10."),
        (350, 114, "Teljesítés dátuma:"), (450, 114, "2026.03.09."),
        (350, 126, "Fizetési határidő:"), (450, 126, "2026.04.09."),
        (350, 138, "Pénznem:"), (450, 138, "EUR"),
        (300, 260, "Nettó összesen"), (470, 260, "1 000,00 EUR"),
        (300, 272, "ÁFA összesen (27%)"), (470, 272, "270,00 EUR"),
        (300, 284, "Fizetendő összesen", True), (470, 284, "1 270,00 EUR", True),
        (40, 320, "Az ÁFA összege forintban: 107 168 Ft (MNB árfolyam: 1 EUR = 396,92 HUF)"),
    ]])
    ex = extract(pdf)
    assert (ex.gross_total, ex.currency, ex.direction) == (Decimal("1270.00"), "EUR", "kimeno")
    assert ex.partner.tax_ids == ["HU87654321"]


def test_bare_total_label_with_net_vat_check():
    pdf = make_pdf([[
        (40, 40, "Studio Rossi S.r.l.", True), (40, 52, "P.IVA: IT12345678901"),
        (40, 90, "Cliente", True), (40, 102, "Nordwind Solutions Kft."), (40, 114, "P.IVA: HU26481937"),
        (350, 90, "Fattura n."), (450, 90, "88/2026"),
        (350, 102, "Data emissione"), (450, 102, "05/07/2026"),
        (350, 114, "Data consegna"), (450, 114, "30/06/2026"),
        (350, 126, "Scadenza"), (450, 126, "04/08/2026"),
        (40, 200, "Descrizione"), (300, 200, "Totale"),
        (40, 212, "Consulenza"), (300, 212, "500,00"),
        (300, 260, "Imponibile"), (470, 260, "500,00 €"),
        (300, 272, "IVA 0%"), (470, 272, "0,00 €"),
        (300, 284, "Totale", True), (470, 284, "500,00 €", True),
    ]])
    ex = extract(pdf)
    assert (ex.invoice_no, ex.direction) == ("88/2026", "bejovo")
    assert (ex.issue_date, ex.supply_date, ex.due_date) == (date(2026, 7, 5), date(2026, 6, 30), date(2026, 8, 4))
    assert (ex.gross_total, ex.currency) == (Decimal("500.00"), "EUR")
    assert not ex.warnings


def test_invoice_without_our_company_is_error():
    pdf = make_pdf([[
        (40, 40, "Alpha Kft.", True), (40, 52, "Adószám: 11111111-2-41"),
        (40, 90, "Vevő:", True), (40, 102, "Beta Kft."), (40, 114, "Adószám: 22222222-2-42"),
        (350, 90, "Számlaszám:"), (450, 90, "A-1"),
    ]])
    ex = extract(pdf)
    assert ex.direction is None
    assert any("irány" in e for e in ex.errors)


@pytest.mark.parametrize("data", [
    b"not a pdf", b"%PDF-1.4\n%broken", make_pdf([[]]),
    "# Markdown\n\nSzámlaszám: X-1\nFizetendő: 100 Ft\n".encode() * 20,
])
def test_unreadable_pdf_raises(data):
    with pytest.raises(PdfReadError):
        extract(data)


def _hu_invoice(no_line: str) -> bytes:
    return make_pdf([[
        (40, 40, "SZÁMLA", True),
        (40, 70, "Eladó:", True), (300, 70, "Vevő:", True),
        (40, 84, "Kis Pék Kft."), (300, 84, "Nordwind Solutions Kft."),
        (40, 108, "Adószám: 12345678-2-41"), (300, 108, "Adószám: 26481937-2-43"),
        (40, 150, no_line),
        (40, 162, "Számla kelte: 2026.05.10."),
        (40, 174, "Teljesítés kelte: 2026.05.08."),
        (40, 186, "Esedékesség: 2026.05.25."),
        (300, 260, "Nettó összeg:"), (450, 260, "100 000 Ft"),
        (300, 272, "ÁFA összeg:"), (450, 272, "27 000 Ft"),
        (300, 284, "Bruttó végösszeg:", True), (450, 284, "127 000 Ft", True),
    ]])


@pytest.mark.parametrize("line, expected", [
    ("Számla sorszáma: PT 2026 1", "PT 2026 1"),
    ("Számla sorszáma: 2026 000123", "2026 000123"),
    ("Számla sorszáma: KP-2026/77", "KP-2026/77"),
    ("Számla sorszáma: KP-2026/77 2026.05.10.", "KP-2026/77"),
])
def test_invoice_number_with_spaces(line, expected):
    assert extract(_hu_invoice(line)).invoice_no == expected


def test_truncated_pdf_message_says_damaged():
    sample = next(SAMPLES_DIR.glob("*.pdf")).read_bytes()
    with pytest.raises(PdfReadError, match="Sérült vagy csonka"):
        extract(sample[: len(sample) // 3])


def test_image_only_pdf_message_says_scanned():
    with pytest.raises(PdfReadError, match="szkennelt"):
        extract(make_pdf([[]]))
