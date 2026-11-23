"""Adóazonosítók felismerése és egységes kulcsra hozása."""
from __future__ import annotations

import re

_HU_DOMESTIC = re.compile(r"\b(\d{8})-(\d)-(\d{2})\b")
_EU_VAT = re.compile(
    r"\b(AT ?U\d{8}|BE ?0?\d{9}|BG\d{9,10}|CY\d{8}[A-Z]|CZ\d{8,10}|DE ?\d{9}|DK ?\d{8}|EE\d{9}|EL\d{9}"
    r"|ES ?[A-Z0-9]\d{7}[A-Z0-9]|FI\d{8}|FR ?[A-Z0-9]{2} ?\d{9}|HR\d{11}|HU ?\d{8}|IE\d{7}[A-Z]{1,2}"
    r"|IT ?\d{11}|LT\d{9,12}|LU\d{8}|LV\d{11}|MT\d{8}|NL\d{9}B\d{2}|PL ?\d{10}|PT ?\d{9}|RO\d{2,10}"
    r"|SE\d{12}|SI\d{8}|SK\d{10}|GB ?\d{3} ?\d{4} ?\d{2}(?: ?\d{3})?|XI\d{9}|CHE-?\d{3}\.\d{3}\.\d{3})\b"
)
_LABELLED = re.compile(
    r"(?i)\b(EIN|TIN|NIP|REGON|SIRET|SIREN|Steuernummer|St\.?-?Nr\.?|Codice fiscale|NIF|CIF|Tax ID|Tax No\.?)"
    r"\s*[:.]?\s*([A-Z]{0,2}[\d][\d \-./]{5,20}\d)"
)


def normalize(raw: str) -> str:
    return re.sub(r"[\s\-./]", "", raw).upper()


def find_tax_ids(text: str) -> list[str]:
    """A szövegben talált adóazonosítók egységes kulccsal (HU belföldi -> HU + 8 jegy)."""
    found: list[str] = []
    for m in _HU_DOMESTIC.finditer(text):
        found.append("HU" + m.group(1))
    for m in _EU_VAT.finditer(text):
        found.append(normalize(m.group(1)))
    for m in _LABELLED.finditer(text):
        label, value = m.group(1).upper(), normalize(m.group(2))
        if _HU_DOMESTIC.search(m.group(2)):
            continue
        if label == "NIP" and re.fullmatch(r"\d{10}", value):
            value = "PL" + value
        elif label in ("EIN", "TIN"):
            value = f"{label}{value}"
        found.append(value)
    seen: list[str] = []
    for f in found:
        if f not in seen:
            seen.append(f)
    return seen
