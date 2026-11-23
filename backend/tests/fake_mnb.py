"""Hamis MNB-szerver a valódi válaszformátumban (escape-elt belső XML, tizedesvessző)."""
import re
from datetime import date
from xml.sax.saxutils import escape

import httpx

# Valós MNB-jegyzések (2026-03-06 és 03-10 között); 03-07, 03-08 hétvége.
QUOTES = {
    date(2026, 3, 6): {"EUR": ("391,29", 1), "USD": ("338,05", 1), "JPY": ("226,10", 100)},
    date(2026, 3, 9): {"EUR": ("396,92", 1), "USD": ("343,53", 1), "JPY": ("229,00", 100)},
    date(2026, 3, 10): {"EUR": ("384,86", 1), "USD": ("330,30", 1), "JPY": ("221,50", 100)},
}


class FakeMnb:
    def __init__(self, quotes):
        self.quotes = quotes
        self.requests = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        body = request.content.decode()
        start = date.fromisoformat(re.search(r"<web:startDate>(.*?)<", body).group(1))
        end = date.fromisoformat(re.search(r"<web:endDate>(.*?)<", body).group(1))
        currs = re.search(r"<web:currencyNames>(.*?)<", body).group(1).split(",")
        self.requests.append((start, end, tuple(currs)))
        days = ""
        for d in sorted(self.quotes, reverse=True):
            if start <= d <= end:
                rates = "".join(f'<Rate unit="{u}" curr="{c}">{v}</Rate>' for c, (v, u) in self.quotes[d].items() if c in currs)
                days += f'<Day date="{d.isoformat()}">{rates}</Day>'
        inner = escape(f"<MNBExchangeRates>{days}</MNBExchangeRates>")
        xml = (
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
            '<GetExchangeRatesResponse xmlns="http://www.mnb.hu/webservices/">'
            f"<GetExchangeRatesResult>{inner}</GetExchangeRatesResult></GetExchangeRatesResponse></s:Body></s:Envelope>"
        )
        return httpx.Response(200, content=xml.encode())
