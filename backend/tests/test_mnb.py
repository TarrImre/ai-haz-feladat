"""MNB-modul: válasz-értelmezés, árfolyam-választás, tárolás, kerekítés."""
from datetime import date, timedelta
from decimal import Decimal

import httpx
import pytest

from app import db
from app.mnb import MnbClient, MnbError, Rate, RateService, parse_rates_xml, to_huf
from tests.fake_mnb import QUOTES, FakeMnb


@pytest.fixture
def fake():
    return FakeMnb(QUOTES)


@pytest.fixture
def service(fake):
    conn = db.connect(":memory:")
    client = MnbClient("http://mnb.test/arfolyamok.asmx", transport=httpx.MockTransport(fake))
    return RateService(conn, client, today=date(2026, 11, 23))


def test_parse_inner_xml_comma_decimal_and_unit():
    rates = parse_rates_xml('<MNBExchangeRates><Day date="2026-11-13"><Rate unit="1" curr="EUR">365,67000</Rate>'
                            '<Rate unit="100" curr="JPY">232,50</Rate></Day></MNBExchangeRates>')
    assert rates == [Rate(date(2026, 11, 13), "EUR", Decimal("365.67000"), 1), Rate(date(2026, 11, 13), "JPY", Decimal("232.50"), 100)]


def test_rate_on_quoted_day(service):
    r = service.rate_for("EUR", date(2026, 3, 9))
    assert (r.day, r.rate) == (date(2026, 3, 9), Decimal("396.92"))


@pytest.mark.parametrize("day", [date(2026, 3, 7), date(2026, 3, 8)])
def test_weekend_uses_last_previous_quote(service, day):
    r = service.rate_for("EUR", day)
    assert (r.day, r.rate) == (date(2026, 3, 6), Decimal("391.29"))


def test_never_uses_later_quote(service):
    assert service.rate_for("USD", date(2026, 3, 8)).day == date(2026, 3, 6)


def test_unit_is_respected():
    jpy = Rate(date(2026, 3, 9), "JPY", Decimal("229.00"), 100)
    assert to_huf(Decimal("10000"), jpy) == 22900


@pytest.mark.parametrize("amount,rate,expected", [
    ("1.00", "100.50", 101),
    ("1.00", "100.49", 100),
    ("1153.16", "396.92", 457712),
    ("-1.00", "100.50", -101),
])
def test_rounding_half_up(amount, rate, expected):
    assert to_huf(Decimal(amount), Rate(date(2026, 1, 1), "EUR", Decimal(rate), 1)) == expected


def test_huf_needs_no_call(service, fake):
    r = service.rate_for("HUF", date(2026, 3, 8))
    assert r.per_unit == 1 and fake.requests == []


def test_stored_rates_are_not_requested_again(service, fake):
    service.rate_for("EUR", date(2026, 3, 9))
    service.rate_for("EUR", date(2026, 3, 8))
    service.rate_for("EUR", date(2026, 3, 7))
    assert len(fake.requests) == 1


def test_prefetch_batches_all_currencies_in_one_call(service, fake):
    needs = [("EUR", date(2026, 3, 9)), ("USD", date(2026, 3, 7)), ("HUF", date(2026, 3, 1))]
    service.prefetch(needs)
    for c, d in needs:
        service.rate_for(c, d)
    assert len(fake.requests) == 1
    start, end, currs = fake.requests[0]
    assert (end, set(currs)) == (date(2026, 3, 9), {"EUR", "USD"})
    assert start <= date(2026, 3, 7) - timedelta(days=7)


def test_persisted_across_service_instances(fake, tmp_path):
    path = tmp_path / "x.sqlite"
    transport = httpx.MockTransport(fake)
    RateService(db.connect(path), MnbClient("http://mnb.test", transport=transport), date(2026, 11, 23)).rate_for("EUR", date(2026, 3, 9))
    RateService(db.connect(path), MnbClient("http://mnb.test", transport=transport), date(2026, 11, 23)).rate_for("EUR", date(2026, 3, 8))
    assert len(fake.requests) == 1


def test_long_gap_extends_lookback(fake):
    fake.quotes = {date(2026, 1, 2): {"EUR": ("400,00", 1)}}
    service = RateService(db.connect(":memory:"), MnbClient("http://mnb.test", transport=httpx.MockTransport(fake)), date(2026, 11, 23))
    r = service.rate_for("EUR", date(2026, 1, 25))
    assert r.day == date(2026, 1, 2)
    assert len(fake.requests) == 2


def test_today_without_quote_is_not_cached_as_covered(fake):
    today = date(2026, 3, 11)
    service = RateService(db.connect(":memory:"), MnbClient("http://mnb.test", transport=httpx.MockTransport(fake)), today)
    assert service.rate_for("EUR", today).day == date(2026, 3, 10)
    fake.quotes[today] = {"EUR": ("390,00", 1)}
    assert service.rate_for("EUR", today).day == today


def test_unknown_currency_raises(service):
    with pytest.raises(MnbError):
        service.rate_for("XYZ", date(2026, 3, 9))


def test_network_error_raises():
    def boom(request):
        raise httpx.ConnectError("down")
    service = RateService(db.connect(":memory:"), MnbClient("http://mnb.test", transport=httpx.MockTransport(boom)), date(2026, 11, 23))
    with pytest.raises(MnbError):
        service.rate_for("EUR", date(2026, 3, 9))
