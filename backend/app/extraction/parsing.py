"""Nyelvfüggetlen dátum-, összeg- és pénznem-értelmezés."""
from __future__ import annotations

import re
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

MONTHS: dict[str, int] = {}
_MONTH_NAMES = {
    1: "january jan januar jänner janvier enero gennaio styczen stycznia januari január",
    2: "february feb februar fevrier février febrero febbraio luty lutego februári február",
    3: "march mar marz märz mars marzo marzec marca március",
    4: "april apr avril abril aprile kwiecien kwietnia kwiecień április",
    5: "may mai mayo maggio maj maja május",
    6: "june jun juni juin junio giugno czerwiec czerwca június",
    7: "july jul juli juillet julio luglio lipiec lipca július",
    8: "august aug aout août agosto sierpien sierpnia sierpień augusztus",
    9: "september sep sept septembre septiembre setiembre settembre wrzesien wrzesnia września szeptember",
    10: "october oct oktober octobre octubre ottobre pazdziernik pazdziernika października október",
    11: "november nov novembre noviembre listopad listopada",
    12: "december dec dezember decembre décembre diciembre dicembre grudzien grudnia grudzień",
}


def _fold(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if not unicodedata.combining(c))


for _num, _names in _MONTH_NAMES.items():
    for _n in _names.split():
        MONTHS[_fold(_n)] = _num

_MONTH_RE = r"([A-Za-zÀ-ÿĀ-žłŁ]{3,}\.?)"
_DATE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(\d{4})[.\-/]\s?(\d{1,2})[.\-/]\s?(\d{1,2})\b\.?"), "ymd"),
    (re.compile(r"\b(\d{1,2})[./\-](\d{1,2})[./\-](\d{4})\b"), "dmy"),
    (re.compile(r"\b(\d{4})\.?\s+" + _MONTH_RE + r"\s+(\d{1,2})\.?"), "y_mon_d"),
    (re.compile(r"\b(\d{1,2})\.?\s+(?:de\s+)?" + _MONTH_RE + r"\s+(?:de\s+)?(\d{4})\b"), "d_mon_y"),
    (re.compile(_MONTH_RE + r"\s+(\d{1,2}),?\s+(\d{4})\b"), "mon_d_y"),
]


def _safe_date(y: int, m: int, d: int) -> date | None:
    try:
        return date(y, m, d)
    except ValueError:
        return None


def parse_date(text: str) -> date | None:
    """Az első értelmezhető dátum a szövegben, különben None."""
    if not text:
        return None
    for pattern, kind in _DATE_PATTERNS:
        for m in pattern.finditer(text):
            g = m.groups()
            if kind == "ymd":
                result = _safe_date(int(g[0]), int(g[1]), int(g[2]))
            elif kind == "dmy":
                a, b, y = int(g[0]), int(g[1]), int(g[2])
                # Európai sorrend az alap; ha a második tag nem lehet hónap, amerikai.
                result = _safe_date(y, b, a) if b <= 12 else _safe_date(y, a, b)
            elif kind == "y_mon_d":
                mon = MONTHS.get(_fold(g[1]).rstrip("."))
                result = _safe_date(int(g[0]), mon, int(g[2])) if mon else None
            elif kind == "d_mon_y":
                mon = MONTHS.get(_fold(g[1]).rstrip("."))
                result = _safe_date(int(g[2]), mon, int(g[0])) if mon else None
            else:
                mon = MONTHS.get(_fold(g[0]).rstrip("."))
                result = _safe_date(int(g[2]), mon, int(g[1])) if mon else None
            if result:
                return result
    return None


CURRENCY_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP", "ft": "HUF", "zł": "PLN", "zl": "PLN", "fr.": "CHF"}
ISO_CURRENCIES = {
    "HUF", "EUR", "USD", "GBP", "PLN", "CHF", "CZK", "RON", "SEK", "NOK", "DKK", "JPY", "CAD", "AUD", "CNY",
    "HRK", "BGN", "RSD", "TRY", "UAH", "RUB",
}

_AMOUNT_RE = re.compile(r"[-−]?\d[\d   '.,]*\d|[-−]?\d")


def _normalize_number(raw: str) -> Decimal | None:
    s = raw.replace(" ", " ").replace(" ", " ").replace("'", " ").replace("−", "-").strip()
    neg = s.startswith("-")
    s = s.lstrip("-").strip()
    last_dot, last_comma = s.rfind("."), s.rfind(",")
    if last_dot >= 0 and last_comma >= 0:
        dec = "." if last_dot > last_comma else ","
    elif last_dot >= 0 or last_comma >= 0:
        sep = "." if last_dot >= 0 else ","
        tail = s[s.rfind(sep) + 1:]
        # Több azonos jel, vagy egy jel pontosan 3 jeggyel: ezres tagolás.
        dec = None if s.count(sep) > 1 or len(tail) == 3 else sep
    else:
        dec = None
    if dec:
        int_part, frac = s.rsplit(dec, 1)
        int_part = re.sub(r"[ .,]", "", int_part)
        s = f"{int_part}.{frac}"
    else:
        s = re.sub(r"[ .,]", "", s)
    if not re.fullmatch(r"\d+(\.\d+)?", s):
        return None
    try:
        value = Decimal(s)
    except InvalidOperation:
        return None
    return -value if neg else value


def detect_currency(text: str) -> str | None:
    """ISO-kód vagy pénzjel a szövegben."""
    for code in re.findall(r"\b[A-Z]{3}\b", text):
        if code in ISO_CURRENCIES:
            return code
    low = text.lower()
    for sym, code in CURRENCY_SYMBOLS.items():
        if sym in ("ft", "zl", "zł"):
            if re.search(rf"(?<![a-zá-ű]){re.escape(sym)}\b", low):
                return code
        elif sym in low:
            return code
    return None


def parse_amount(text: str) -> tuple[Decimal, str | None] | None:
    """Összeg és (ha van) pénznem egy cellából; százalékot, dátumot nem fogad el."""
    if not text or "%" in text or parse_date(text):
        return None
    matches = _AMOUNT_RE.findall(text)
    if not matches:
        return None
    raw = max(matches, key=lambda m: len(re.sub(r"\D", "", m)))
    value = _normalize_number(raw)
    if value is None:
        return None
    return value, detect_currency(text)
