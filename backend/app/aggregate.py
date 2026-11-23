"""Összesítés: havi bontás fizetési határidő szerint, partnerenkénti táblázat."""
from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from app.extraction.vocab import fold


@dataclass(frozen=True)
class InvoiceFacts:
    direction: str
    due_date: date
    huf_total: int
    partner_name: str
    partner_tax_ids: tuple[str, ...]


@dataclass
class MonthRow:
    month: str
    incoming: int = 0
    outgoing: int = 0


@dataclass
class PartnerColumn:
    name: str
    tax_ids: list[str]
    incoming: int = 0
    outgoing: int = 0
    names: list[str] = field(default_factory=list)


def _month_index(d: date) -> int:
    return d.year * 12 + d.month - 1


def monthly(invoices: Iterable[InvoiceFacts]) -> list[MonthRow]:
    """Folyamatos hónapsor a legkorábbi és a legkésőbbi határidő-hónap között, üres hónap 0-val."""
    items = list(invoices)
    if not items:
        return []
    sums: dict[int, MonthRow] = {}
    lo = min(_month_index(i.due_date) for i in items)
    hi = max(_month_index(i.due_date) for i in items)
    for idx in range(lo, hi + 1):
        sums[idx] = MonthRow(f"{idx // 12:04d}-{idx % 12 + 1:02d}")
    for i in items:
        row = sums[_month_index(i.due_date)]
        if i.direction == "bejovo":
            row.incoming += i.huf_total
        else:
            row.outgoing += i.huf_total
    return [sums[k] for k in range(lo, hi + 1)]


def name_key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", fold(name))


def _display_name(names: list[str]) -> str:
    """A nem csupa nagybetűs írásmód elsőbbséget kap, azon belül a leggyakoribb."""
    counts = Counter(names)
    return max(counts, key=lambda n: (not n.isupper(), counts[n], -len(n)))


def partners(invoices: Iterable[InvoiceFacts]) -> list[PartnerColumn]:
    """Partnerek összevonása közös adóazonosító vagy azonos normalizált név alapján (unió-keresés)."""
    items = list(invoices)
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    keys_per_invoice = []
    for inv in items:
        keys = [f"id:{t}" for t in inv.partner_tax_ids] + [f"name:{name_key(inv.partner_name)}"]
        for k in keys[1:]:
            union(keys[0], k)
        keys_per_invoice.append(keys)

    groups: dict[str, PartnerColumn] = {}
    members: dict[str, list[InvoiceFacts]] = defaultdict(list)
    for inv, keys in zip(items, keys_per_invoice):
        members[find(keys[0])].append(inv)
    for root, invs in members.items():
        ids: list[str] = []
        for inv in invs:
            ids += [t for t in inv.partner_tax_ids if t not in ids]
        col = PartnerColumn(name=_display_name([i.partner_name for i in invs]), tax_ids=ids,
                            names=sorted({i.partner_name for i in invs}))
        for inv in invs:
            if inv.direction == "bejovo":
                col.incoming += inv.huf_total
            else:
                col.outgoing += inv.huf_total
        groups[root] = col
    return sorted(groups.values(), key=lambda c: (-(c.incoming + c.outgoing), c.name))
