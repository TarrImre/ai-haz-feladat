"""Többnyelvű címkeszótár: mezőnként a címkék ékezet nélküli, kisbetűs reguláris kifejezései."""
from __future__ import annotations

import re
import unicodedata


def fold(s: str) -> str:
    s = "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))
    return " ".join(s.replace("ł", "l").replace("ß", "ss").split())


LABELS: dict[str, list[str]] = {
    "invoice_no": [
        r"szamlaszam", r"szamla sorszama", r"szamla szama", r"sorszam",
        r"invoice (no\.?|number|nr\.?|#)", r"inv\.? no\.?", r"bill no\.?",
        r"rechnungs(nummer|nr\.?)", r"rechnung (nr\.?|nummer)", r"beleg(nummer|nr\.?)",
        r"n[°ºo]\.? de (facture|factura)", r"numero de (facture|factura)", r"facture n[°ºo]\.?", r"factura n[°ºo]\.?",
        r"fattura (n\.?|nr\.?|numero)", r"numero fattura", r"n\.? fattura",
        r"numer faktury", r"faktura (nr|numer)", r"nr faktury",
    ],
    "issue_date": [
        r"kiallitas (datuma|kelte)", r"szamla kelte", r"kelte", r"kiallitva",
        r"invoice date", r"date of issue", r"issue date", r"date issued", r"billing date",
        r"rechnungsdatum", r"ausstellungsdatum", r"datum",
        r"date de (facture|facturation|l'?emission|emission)", r"date d'?emission",
        r"fecha( de)? (emision|factura|expedicion)",
        r"data (fattura|emissione|documento)",
        r"data wystawienia",
    ],
    "supply_date": [
        r"teljesites (datuma|kelte|idopontja)", r"teljesites",
        r"date of (supply|service|delivery)", r"(supply|service|delivery|performance) date", r"tax point( date)?",
        r"leistungsdatum", r"lieferdatum", r"leistungszeitpunkt", r"liefer-? ?/ ?leistungsdatum",
        r"date de (prestation|livraison|la prestation)",
        r"fecha( de)? (operacion|prestacion|entrega|servicio)",
        r"data (prestazione|consegna|operazione|effettuazione)",
        r"data (sprzedazy|dostawy|wykonania( uslugi)?)",
    ],
    "due_date": [
        r"fizetesi hatarido", r"esedekesseg( datuma)?", r"hatarido",
        r"due date", r"payment due( date)?", r"due by", r"pay by", r"payable by",
        r"falligkeit(sdatum)?", r"zahlbar bis", r"fallig (am|bis)", r"zahlungsfrist bis",
        r"date d'?echeance", r"echeance", r"a regler avant le",
        r"fecha( de)? vencimiento", r"vencimiento",
        r"data (di )?scadenza", r"scadenza( pagamento)?",
        r"termin platnosci", r"termin zaplaty",
    ],
    "currency": [
        r"penznem", r"currency", r"wahrung", r"devise", r"moneda", r"valuta", r"divisa", r"waluta",
    ],
    "total": [
        r"fizetendo( osszesen| osszeg| vegosszeg)?", r"brutto (vegosszeg|osszesen|osszeg)", r"vegosszeg", r"szamla vegosszege",
        r"total (due|amount due|payable|to pay)", r"amount (due|payable)", r"balance due", r"grand total", r"invoice total",
        r"total \(?incl\.? (vat|tax)\)?", r"total gross", r"gross total",
        r"rechnungsbetrag", r"gesamtbetrag", r"zu zahlen(der betrag)?", r"endbetrag", r"zahlbetrag", r"gesamt brutto", r"bruttobetrag",
        r"net a payer( ttc)?", r"total ttc", r"montant ttc", r"montant (total|a payer)", r"total a payer",
        r"total (a pagar|factura|importe)", r"importe total", r"total con iva",
        r"totale (documento|da pagare|fattura)", r"importo totale", r"netto a pagare",
        r"do zaplaty", r"razem do zaplaty", r"kwota do zaplaty", r"razem brutto", r"wartosc brutto razem",
    ],
    "total_weak": [
        r"total", r"osszesen", r"mindosszesen", r"summe", r"gesamt", r"totale", r"razem", r"importe",
    ],
    "net": [
        r"netto osszesen", r"netto osszeg", r"osszesen netto",
        r"subtotal", r"sub-total", r"total net", r"net total", r"total excl\.? (vat|tax)", r"total before tax",
        r"gesamt netto", r"nettobetrag", r"summe netto", r"zwischensumme", r"netto gesamt",
        r"total ht", r"montant ht", r"total hors taxes",
        r"(total )?base imponible( total)?", r"total neto", r"importe neto",
        r"(totale )?imponibile", r"totale netto",
        r"razem netto", r"wartosc netto razem", r"suma netto",
    ],
    "vat": [
        r"afa osszesen", r"afa osszeg", r"osszesen afa",
        r"vat total", r"total vat", r"vat amount", r"tax total", r"total tax", r"vat",
        r"ust\.?( gesamt| summe)?", r"mwst\.?( gesamt)?", r"umsatzsteuer", r"summe ust\.?",
        r"total tva", r"tva", r"montant tva",
        r"(total )?iva", r"cuota iva",
        r"totale iva", r"imposta",
        r"razem vat", r"kwota vat", r"suma vat",
    ],
    "buyer": [
        r"vevo", r"vasarlo", r"megrendelo",
        r"bill to", r"billed to", r"invoice to", r"customer", r"buyer", r"client", r"sold to",
        r"rechnungsempfanger", r"kunde", r"auftraggeber", r"leistungsempfanger",
        r"facture a", r"factur[ee] a", r"client", r"destinataire",
        r"cliente", r"facturar a", r"destinatario",
        r"cessionario( ?/ ?committente)?", r"committente",
        r"nabywca", r"odbiorca",
    ],
    "seller": [
        r"elado", r"szallito", r"kiallito", r"szolgaltato",
        r"seller", r"supplier", r"vendor", r"from", r"bill from",
        r"verkaufer", r"lieferant", r"rechnungssteller", r"leistender",
        r"vendeur", r"emetteur", r"fournisseur", r"prestataire",
        r"emisor", r"proveedor", r"vendedor",
        r"cedente( ?/ ?prestatore)?", r"prestatore", r"fornitore",
        r"sprzedawca", r"dostawca", r"wystawca",
    ],
    "tax_id": [
        r"adoszam", r"kozossegi adoszam", r"eu adoszam", r"csoportazonosito",
        r"tax id", r"tax no\.?", r"vat (no\.?|number|id|reg\.? no\.?)", r"tin", r"ein", r"company no\.?",
        r"ust-?id(nr\.?)?", r"ust-?idnr\.?", r"steuernummer", r"st\.?-?nr\.?", r"uid",
        r"n[°º]? tva( intracom\.?| intracommunautaire)?", r"identifiant fiscal", r"siret", r"siren", r"tva intracom\.?",
        r"nif(-iva)?", r"cif", r"n[°º] de identificacion fiscal", r"nif\/cif",
        r"partita iva", r"p\.? ?iva", r"codice fiscale",
        r"nip", r"nr identyfikacji podatkowej", r"regon",
    ],
}

_COMPILED = {k: [re.compile(rf"^(?:{p})$") for p in v] for k, v in LABELS.items()}


def label_parts(text: str) -> list[str]:
    """Egy (esetleg kétnyelvű) címke részei, ékezet és záró kettőspont nélkül."""
    t = re.sub(r"\([^)]*\)|\d+(?:[.,]\d+)?\s*%", " ", fold(text))
    t = " ".join(t.split()).rstrip(":").strip()
    parts = [t] + [p.strip().rstrip(":").strip() for p in re.split(r"\s+/\s+|\s+\|\s+", t)]
    return [p for p in parts if p]


def match_field(text: str) -> str | None:
    """Melyik mező címkéje ez a szöveg (teljes egyezés valamelyik nyelvi részre)."""
    parts = label_parts(text)
    for field, patterns in _COMPILED.items():
        for part in parts:
            if any(p.match(part) for p in patterns):
                return field
    return None


def is_field(text: str, field: str) -> bool:
    parts = label_parts(text)
    return any(p.match(part) for part in parts for p in _COMPILED[field])
