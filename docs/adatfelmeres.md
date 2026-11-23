# Adatfelmérés - a 100 mintaszámla (2026-11-23)

Szkriptek: [backend/scripts/survey.py](../backend/scripts/survey.py), [backend/scripts/labels.py](../backend/scripts/labels.py). A kimenetük
(`backend/scripts/out/`) nincs a repóban, újragenerálható.

## Összkép

- 100 PDF, mind szöveges (ReportLab), 98 egyoldalas, 2 kétoldalas. A kétoldalasaknál a végösszeg a 2. oldalon van.
- 100 különböző számlaszám, a csomagban nincs duplikátum (a duplikáció-szűrést saját teszttel kell igazolni).
- Pénznemek (előfordulás a szövegben): EUR 46, HUF 38, USD 6, PLN 6, GBP 5.
- Jóváíró, sztornó, előleg, kedvezmény, kerekítési sor nincs a mintában.
- Kiállító szerint öt sablon (a PDF `creator` mezője): SAP Business One, BillFlow Cloud, Nordwind ERP 4.2,
  DocuSign Pro Office, InvoiceKit 2.1. Egy sablon több nyelven és több kiállítónál is előfordul, és a rejtett
  teszt új sablont is hozhat, ezért a kinyerés **nem épülhet a sablon felismerésére**.
- Partnerek (12): Duna Logisztika, Pannon Irodaszer, Kovács és Társa, Balaton Tech, Brenner Maschinenbau,
  Hoffmann & Söhne, Wisła Software, Lumière Conseil, Soluciones Ibéricas, Officina Romano, Greenfield Analytics,
  Atlas Cloud. Több partner mindkét irányban szerepel.

## Elrendezés: miért nem elég a sima szöveg

- A `pdftotext -layout` több sablonnál összecsúsztatja az oszlopokat ("Tota8l d5u4e5,00"), a címke és az érték
  elválik egymástól.
- A PyMuPDF `get_text("dict")` viszont **tiszta span-eket** ad koordinátával: a címke és az érték külön span.
- Két elrendezés-minta fordul elő: **az érték a címke mellett jobbra** (ugyanabban a sorban), vagy **alatta**
  (ugyanabban az oszlopban). Kétnyelvű sablonnál a címke `Magyar / English`.

## Csapdák a mintában

| Csapda | Példa | Kezelés |
|---|---|---|
| Ugyanaz a címke dátumra és fizetési feltételre | `Termin płatności: 23.03.2026` és `Termin płatności: 14 dni` | a címke értéke csak akkor dátum, ha dátumként értelmezhető |
| Forintos ÁFA-sor deviza-számlán | `Az ÁFA összege forintban: 97 309 Ft (MNB árfolyam: 1 EUR = 396,92 HUF)` | ez nem végösszeg; az árfolyamot mindig az MNB-ből kérjük |
| Nettó, ÁFA, bruttó egymás alatt | `Nettó összesen`, `ÁFA összesen`, `Fizetendő összesen` | a "fizetendő" címkék szótára; ellenőrzés: nettó + ÁFA = bruttó |
| Végösszeg a 2. oldalon | PI-26-0050, PI-26-0023 | minden oldal együtt |
| Számlaszám-írásmód | a fájlnév `DL-2026-00008`, a számlán `DL/2026/00008` | csak a PDF szövege számít |
| Csak közösségi adószám | Pannon Irodaszer: csak `HU23918466` | partner-kulcs: belföldi `12345678-x-yy` -> `HU12345678` |
| Adószám nélküli partner | Atlas Cloud: csak `EIN 84-3920175` | partner-kulcs: bármely adóazonosító, végső esetben a normalizált név |
| Betűritkított cím | `S Z Á M L A`, `R E C H N U N G` | a dokumentumtípus nem kell a kinyeréshez |

## Formátumok

- Dátum: `2026.03.15.`, `15.03.2026`, `15/03/2026`, `15 March 2026`, `March 15, 2026`, `15. März 2026`,
  `15 mars 2026`, `2026. március 15.`. Hónapnevek HU/EN/DE/FR/ES/IT/PL. A `/`-es forma a mintában mindig nap/hónap.
- Szám: `1 234,56`, `1.234,56`, `1,234.56`, HUF-nál tizedes nélkül (`121 158`), pénzjellel vagy anélkül
  (`€5,452.00`, `£`, `$`, `Ft`, `HUF`, `EUR`).

## MNB-szolgáltatás

- A `GetExchangeRates` 2026-ra ad adatot, a napok csökkenő sorrendben jönnek, a tizedesjel vessző.
- Kontroll: az NW-2026-0014-re nyomtatott árfolyam (1 EUR = 396,92 HUF) egyezik az MNB 2026-03-09-i
  jegyzésével, ami a számla teljesítési napja. Ez megerősíti, hogy a teljesítési nap a helyes kulcs.
