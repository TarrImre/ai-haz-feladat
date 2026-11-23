"""Szabályalapú kinyerés: címke-érték párosítás koordináták alapján, nyelv- és sablonfüggetlenül."""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from app import config
from app.extraction import taxid, vocab
from app.extraction.parsing import detect_currency, parse_amount, parse_date, ISO_CURRENCIES
from app.extraction.pdf_spans import Span, full_text, load_spans

LEGAL_FORM = re.compile(
    r"(?i)\b(kft|zrt|nyrt|bt|kkt|ev|gmbh|ag|kg|ohg|ug|e\.?k|sarl|sas|sa|s\.?a\.?s|eurl|s\.?l\.?u?|s\.?a\.?|"
    r"s\.?r\.?l\.?|s\.?p\.?a\.?|sp\.? ?z ?o\.? ?o|s\.?c\.?|ltd|limited|plc|llp|inc|llc|corp|co|b\.?v|n\.?v|oy|ab|as|a/s|s\.?r\.?o)\.?$"
)
DOC_TITLES = re.compile(
    r"(?i)^(s ?z ?a ?m ?l ?a|invoice|tax invoice|r ?e ?c ?h ?n ?u ?n ?g|f ?a ?c ?t ?u ?r ?e|factura|fattura|faktura( vat)?|"
    r"eredeti peldany|masolat|original|copy|oryginal|kopia)\b"
)


@dataclass
class Party:
    name: str | None = None
    tax_ids: list[str] = field(default_factory=list)


@dataclass
class Extraction:
    invoice_no: str | None = None
    seller: Party = field(default_factory=Party)
    buyer: Party = field(default_factory=Party)
    issue_date: date | None = None
    supply_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    gross_total: Decimal | None = None
    net_total: Decimal | None = None
    vat_total: Decimal | None = None
    direction: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def partner(self) -> Party:
        return self.buyer if self.direction == "kimeno" else self.seller


def _same_line(a: Span, b: Span) -> bool:
    return abs(a.cy - b.cy) < max(a.height, b.height) * 0.55


def _label_and_inline(sp: Span) -> tuple[str, str]:
    if ":" in sp.text:
        lab, val = sp.text.split(":", 1)
        return lab, val.strip()
    return sp.text, ""


class Document:
    def __init__(self, spans: list[Span]):
        self.spans = spans
        self.text = full_text(spans)
        self._fields = [(sp, *self._classify(sp)) for sp in spans]

    @staticmethod
    def _classify(sp: Span) -> tuple[str | None, str]:
        lab, inline = _label_and_inline(sp)
        f = vocab.match_field(lab)
        if f is None and inline:
            f = vocab.match_field(sp.text)
            inline = "" if f else inline
        return f, inline

    def is_label(self, sp: Span) -> bool:
        lab, _ = _label_and_inline(sp)
        return vocab.match_field(lab) is not None

    def right_of(self, label: Span) -> list[Span]:
        cands = [s for s in self.spans if s is not label and s.page == label.page and _same_line(s, label) and s.x0 >= label.x1 - 1]
        return sorted(cands, key=lambda s: s.x0)

    def below(self, label: Span, max_gap: float | None = None) -> list[Span]:
        gap = max_gap if max_gap is not None else label.height * 3.2
        cands = [
            s for s in self.spans
            if s is not label and s.page == label.page and s.y0 >= label.y1 - 1.5 and s.y0 - label.y1 <= gap
            and min(s.x1, label.x1) - max(s.x0, label.x0) > -2 and abs(s.x0 - label.x0) < 60
        ]
        return sorted(cands, key=lambda s: (s.y0, abs(s.x0 - label.x0)))

    def values(self, field_name: str) -> list[tuple[Span, str]]:
        """Az adott mező összes jelölt értéke: soron belül, jobbra, majd alatta."""
        out: list[tuple[Span, str]] = []
        for sp, f, inline in self._fields:
            if f != field_name:
                continue
            if inline:
                out.append((sp, inline))
                continue
            right = [s for s in self.right_of(sp)[:1] if not self.is_label(s)]
            below = [s for s in self.below(sp)[:2] if not self.is_label(s)][:1]
            # Az alatta, vele egy vonalban kezdődő érték erősebb, mint a távoli jobb szomszéd.
            aligned = [s for s in below if abs(s.x0 - sp.x0) < 3 and s.y0 - sp.y1 < sp.height * 1.5]
            for s in (aligned + right + below) if aligned else (right + below):
                if (s, s.text) not in out:
                    out.append((s, s.text))
        return out

    def label_spans(self, field_name: str) -> list[Span]:
        return [sp for sp, f, _ in self._fields if f == field_name]


def _first_date(doc: Document, field_name: str) -> date | None:
    for _, text in doc.values(field_name):
        d = parse_date(text)
        if d:
            return d
    return None


_INVNO_PART = re.compile(r"[A-Z]{1,5}|[A-Za-z0-9/\-._#]*\d[A-Za-z0-9/\-._#]*")


def _invoice_no(doc: Document) -> str | None:
    for _, text in doc.values("invoice_no"):
        parts = text.split()
        # Szóközzel tagolt szám ("PT 2026 1"): az egész érték, ha minden tagja számlaszám-darab.
        if len(parts) > 1 and all(_INVNO_PART.fullmatch(p) and not parse_date(p) for p in parts) and any(c.isdigit() for c in text):
            return " ".join(parts).strip(".")
        m = re.search(r"[A-Za-z0-9][A-Za-z0-9/\-._#]*\d[A-Za-z0-9/\-._]*", text)
        if m and not parse_date(m.group(0)):
            return m.group(0).strip(".")
    return None


def _block_under(doc: Document, label: Span, inline: str) -> list[Span]:
    """A címke alatti, vele egy oszlopban kezdődő, összefüggő sorok (partner-blokk)."""
    block: list[Span] = []
    last = label
    for s in sorted((s for s in doc.spans if s.page == label.page and s.y0 >= label.y1 - 1), key=lambda s: s.y0):
        if abs(s.x0 - label.x0) > 8:
            continue
        if s.y0 - last.y1 > max(label.height, 8) * 2.6:
            break
        if block and doc.is_label(s) and not vocab.is_field(_label_and_inline(s)[0], "tax_id"):
            break
        block.append(s)
        last = s
        if len(block) >= 9:
            break
    return block


def _ours(name: str | None, ids: list[str]) -> bool:
    our_ids = {k for t in config.OUR_TAX_IDS for k in taxid.find_tax_ids(t)} | {taxid.normalize(t) for t in config.OUR_TAX_IDS}
    if any(i in our_ids for i in ids):
        return True
    return bool(name) and _name_key(name) == _name_key(config.OUR_COMPANY_NAME)


def _name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", vocab.fold(name))


def _company_name(spans: list[Span]) -> str | None:
    for s in spans:
        t = s.text.strip()
        if LEGAL_FORM.search(t.rstrip(",")) and not DOC_TITLES.match(vocab.fold(t)):
            return t
    return None


def _party_block(doc: Document, field_name: str) -> list[Span] | None:
    for label in doc.label_spans(field_name):
        lab, inline = _label_and_inline(label)
        block = _block_under(doc, label, inline)
        if inline:
            block = [Span(inline, label.x0, label.y0, label.x1, label.y1, label.page, label.bold, label.size)] + block
        if block:
            return block
    return None


def _parties(doc: Document, ex: Extraction) -> None:
    buyer_block = _party_block(doc, "buyer")
    seller_block = _party_block(doc, "seller")
    all_ids = taxid.find_tax_ids(doc.text)

    if buyer_block:
        ex.buyer.name = _company_name(buyer_block) or buyer_block[0].text
        ex.buyer.tax_ids = taxid.find_tax_ids("\n".join(s.text for s in buyer_block))
    in_buyer = {id(s) for s in buyer_block or []}
    rest = [s for s in doc.spans if id(s) not in in_buyer]

    if seller_block:
        ex.seller.name = _company_name(seller_block) or seller_block[0].text
        ex.seller.tax_ids = taxid.find_tax_ids("\n".join(s.text for s in seller_block))
    else:
        first_page = sorted((s for s in rest if s.page == 0), key=lambda s: (s.y0, s.x0))
        ex.seller.name = _company_name(first_page)
        ex.seller.tax_ids = [t for t in taxid.find_tax_ids(full_text(rest)) if t not in ex.buyer.tax_ids]
    if not ex.buyer.tax_ids and buyer_block is None:
        ex.buyer.tax_ids = [t for t in all_ids if t not in ex.seller.tax_ids]


def _direction(ex: Extraction) -> None:
    buyer_ours = _ours(ex.buyer.name, ex.buyer.tax_ids)
    seller_ours = _ours(ex.seller.name, ex.seller.tax_ids)
    if buyer_ours and not seller_ours:
        ex.direction = "bejovo"
    elif seller_ours and not buyer_ours:
        ex.direction = "kimeno"
    elif buyer_ours:
        ex.errors.append("Nem dönthető el az irány: a cégünk mindkét oldalon szerepel")
    else:
        ex.errors.append("Nem dönthető el az irány: a cégünk egyik oldalon sem szerepel")


def _amounts(doc: Document, field_name: str) -> list[tuple[Decimal, str | None]]:
    out = []
    for _, text in doc.values(field_name):
        a = parse_amount(text)
        if a and a[0] != 0 or (a and field_name == "vat"):
            out.append(a)
    return out


def _totals(doc: Document, ex: Extraction) -> None:
    nets, vats = _amounts(doc, "net"), _amounts(doc, "vat")
    tol = Decimal("0.011")
    # Előbb az erős végösszeg-címkék; több egyező hármasból a legnagyobb végösszeg.
    for field_name in ("total", "total_weak"):
        triples = [(t, n, v) for t, _ in _amounts(doc, field_name) for n, _ in nets for v, _ in vats if abs(n + v - t) <= tol]
        if triples:
            ex.gross_total, ex.net_total, ex.vat_total = max(triples, key=lambda x: x[0])
            return
    totals = _amounts(doc, "total") or _amounts(doc, "total_weak")
    if totals:
        counts = Counter(t for t, _ in totals)
        ex.gross_total = max(counts, key=lambda t: (counts[t], t))
        ex.warnings.append("A végösszeget nem sikerült a nettó + ÁFA összeggel igazolni")
    if nets:
        ex.net_total = nets[0][0]
    if vats:
        ex.vat_total = vats[0][0]


def _currency(doc: Document, ex: Extraction) -> None:
    for _, text in doc.values("currency"):
        code = text.strip().upper()[:3]
        if code in ISO_CURRENCIES:
            ex.currency = code
            break
    total_cur = None
    for a in _amounts(doc, "total") + _amounts(doc, "total_weak"):
        if a[0] == ex.gross_total and a[1]:
            total_cur = a[1]
            break
    if ex.currency and total_cur and total_cur != ex.currency:
        ex.warnings.append(f"A pénznem-mező ({ex.currency}) és a végösszeg pénzneme ({total_cur}) eltér")
    ex.currency = ex.currency or total_cur or detect_currency(doc.text)


REQUIRED = {
    "invoice_no": "számlaszám", "issue_date": "kiállítás dátuma", "supply_date": "teljesítés dátuma",
    "due_date": "fizetési határidő", "currency": "pénznem", "gross_total": "bruttó végösszeg", "direction": "irány",
}


def extract_document(doc: Document) -> Extraction:
    ex = Extraction()
    ex.invoice_no = _invoice_no(doc)
    ex.issue_date = _first_date(doc, "issue_date")
    ex.supply_date = _first_date(doc, "supply_date")
    ex.due_date = _first_date(doc, "due_date")
    _parties(doc, ex)
    _direction(ex)
    _totals(doc, ex)
    _currency(doc, ex)
    if ex.supply_date is None and ex.issue_date:
        ex.supply_date = ex.issue_date
        ex.warnings.append("Nincs teljesítési dátum, a kiállítás dátuma lett használva")
    for attr, name in REQUIRED.items():
        if getattr(ex, attr) is None and not any(name in e for e in ex.errors):
            ex.errors.append(f"Hiányzó mező: {name}")
    if not ex.partner.name:
        ex.errors.append("Hiányzó mező: partner neve")
    if ex.gross_total is not None and ex.gross_total <= 0:
        ex.warnings.append("Nem pozitív végösszeg")
    if ex.due_date and ex.issue_date and ex.due_date < ex.issue_date:
        ex.warnings.append("A fizetési határidő a kiállítás előtt van")
    return ex


def extract(data: bytes) -> Extraction:
    return extract_document(Document(load_spans(data)))
