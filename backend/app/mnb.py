"""MNB-árfolyamok: SOAP-lekérés, tárolás, a teljesítési napra érvényes árfolyam kiválasztása."""
from __future__ import annotations

import sqlite3
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

import httpx

NS = "http://www.mnb.hu/webservices/"
LOOKBACK_DAYS = 14
MAX_LOOKBACK_DAYS = 60


class MnbError(Exception):
    """Az MNB-szolgáltatás nem elérhető, vagy nincs árfolyam."""


@dataclass(frozen=True)
class Rate:
    day: date
    currency: str
    rate: Decimal
    unit: int

    @property
    def per_unit(self) -> Decimal:
        return self.rate / self.unit


def parse_rates_xml(inner_xml: str) -> list[Rate]:
    """A GetExchangeRatesResult belső XML-je (tizedesvessző, unit attribútum)."""
    root = ET.fromstring(inner_xml)
    out = []
    for day in root.iter("Day"):
        d = date.fromisoformat(day.attrib["date"])
        for r in day.iter("Rate"):
            out.append(Rate(d, r.attrib["curr"], Decimal(r.text.strip().replace(",", ".")), int(r.attrib.get("unit", "1"))))
    return out


class MnbClient:
    def __init__(self, endpoint: str, transport: httpx.BaseTransport | None = None, timeout: float = 30):
        self.endpoint = endpoint
        self._http = httpx.Client(transport=transport, timeout=timeout)
        self.calls = 0

    def get_exchange_rates(self, start: date, end: date, currencies: Iterable[str]) -> list[Rate]:
        body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" xmlns:web="http://www.mnb.hu/webservices/">'
            "<soap:Body><web:GetExchangeRates>"
            f"<web:startDate>{start.isoformat()}</web:startDate><web:endDate>{end.isoformat()}</web:endDate>"
            f"<web:currencyNames>{','.join(sorted(set(currencies)))}</web:currencyNames>"
            "</web:GetExchangeRates></soap:Body></soap:Envelope>"
        )
        headers = {
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": '"http://www.mnb.hu/webservices/MNBArfolyamServiceSoap/GetExchangeRates"',
        }
        self.calls += 1
        try:
            resp = self._http.post(self.endpoint, content=body.encode("utf-8"), headers=headers)
            resp.raise_for_status()
            result = ET.fromstring(resp.content).find(f".//{{{NS}}}GetExchangeRatesResult")
        except (httpx.HTTPError, ET.ParseError) as exc:
            raise MnbError(f"MNB-lekérés sikertelen: {exc}") from exc
        if result is None or not (result.text or "").strip():
            return []
        return parse_rates_xml(result.text)


class RateService:
    """Árfolyam a teljesítési napra; ha aznap nincs jegyzés, az azt megelőző utolsó."""

    def __init__(self, conn: sqlite3.Connection, client: MnbClient, today: date | None = None):
        self.conn = conn
        self.client = client
        self._today = today
        self._lock = threading.Lock()

    @property
    def today(self) -> date:
        return self._today or date.today()

    def _covered(self, currency: str, start: date, end: date) -> bool:
        """Minden nap [start, end]-ben szerepel-e valamelyik lekért időszakban."""
        rows = self.conn.execute(
            "SELECT start_day, end_day FROM mnb_coverage WHERE currency=? AND end_day>=? AND start_day<=? ORDER BY start_day",
            (currency, start.isoformat(), end.isoformat()),
        ).fetchall()
        cursor = start
        for r in rows:
            s, e = date.fromisoformat(r["start_day"]), date.fromisoformat(r["end_day"])
            if s > cursor:
                return False
            cursor = max(cursor, e + timedelta(days=1))
            if cursor > end:
                return True
        return cursor > end

    def _latest_stored(self, currency: str, day: date) -> Rate | None:
        r = self.conn.execute(
            "SELECT day, rate, unit FROM mnb_rates WHERE currency=? AND day<=? ORDER BY day DESC LIMIT 1",
            (currency, day.isoformat()),
        ).fetchone()
        return Rate(date.fromisoformat(r["day"]), currency, Decimal(r["rate"]), r["unit"]) if r else None

    def _fetch(self, currencies: set[str], start: date, end: date) -> None:
        rates = self.client.get_exchange_rates(start, end, currencies)
        # A mai (vagy jövőbeli) nap csak akkor számít lefedettnek, ha már van rá jegyzés.
        last_day = max((r.day for r in rates), default=None)
        cover_end = min(end, self.today - timedelta(days=1))
        if last_day and last_day > cover_end:
            cover_end = last_day
        with self.conn:
            self.conn.executemany(
                "INSERT OR REPLACE INTO mnb_rates (day, currency, rate, unit) VALUES (?, ?, ?, ?)",
                [(r.day.isoformat(), r.currency, str(r.rate), r.unit) for r in rates],
            )
            if cover_end >= start:
                self.conn.executemany(
                    "INSERT INTO mnb_coverage (currency, start_day, end_day) VALUES (?, ?, ?)",
                    [(c, start.isoformat(), cover_end.isoformat()) for c in currencies],
                )

    def _resolved(self, currency: str, day: date, allow_pending: bool = False) -> Rate | None:
        r = self._latest_stored(currency, day)
        # Mai/jövőbeli napra friss lekérés után a legutóbbi közzétett jegyzés érvényes.
        check_end = min(day, self.today - timedelta(days=1)) if allow_pending else day
        if r and (check_end < r.day or self._covered(currency, r.day, check_end)):
            return r
        return None

    def prefetch(self, needs: Iterable[tuple[str, date]]) -> None:
        """Egy hívással lekéri a hiányzó időszakot az összes kért devizára."""
        with self._lock:
            missing = [(c, d) for c, d in needs if c != "HUF" and self._resolved(c, d) is None]
            if not missing:
                return
            start = min(d for _, d in missing) - timedelta(days=LOOKBACK_DAYS)
            end = max(d for _, d in missing)
            self._fetch({c for c, _ in missing}, start, end)

    def rate_for(self, currency: str, day: date) -> Rate:
        if currency == "HUF":
            return Rate(day, "HUF", Decimal(1), 1)
        with self._lock:
            r = self._resolved(currency, day)
            lookback = LOOKBACK_DAYS
            while r is None and lookback <= MAX_LOOKBACK_DAYS:
                self._fetch({currency}, day - timedelta(days=lookback), day)
                r = self._resolved(currency, day, allow_pending=True)
                lookback *= 2
        if r is None:
            raise MnbError(f"Nincs MNB-árfolyam: {currency} {day.isoformat()} előtt {MAX_LOOKBACK_DAYS} napon belül")
        return r


def to_huf(amount: Decimal, rate: Rate) -> int:
    """Számlánként egész forintra, 0,5-től felfelé."""
    return int((amount * rate.rate / rate.unit).quantize(Decimal(1), rounding=ROUND_HALF_UP))
