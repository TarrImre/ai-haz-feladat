# Számlafeldolgozó és cash-flow kimutatás

PDF-számlák feltöltése, a mezők kinyerése, forintra váltás a teljesítési nap MNB-árfolyamával, és forintos
kimutatás: havi vonaldiagram fizetési határidő szerint, cégenkénti összesítő, ellenőrizhető számlalista.

## Indítás

Előfeltétel: Docker (Docker Desktop vagy Docker Engine + Compose v2.24+). Más helyi függőség nem kell. Az első buildhez
internet kell (alapképek, pip, npm, a felület betűje a Google Fontsról); futás közben csak az MNB-hez.

```bash
docker compose up --build
```

Az alkalmazás: **http://localhost:8080**

API-kulcs nem kell, mert az alkalmazás nem használ LLM-et (lásd lent), ezért `.env` sincs; a `.env.example` csak ezt rögzíti.

Beállítások: környezeti változók, mind kötelező; ha valamelyik hiányzik, a szolgáltatás hibával leáll, nincs
beégetett alapérték. Az értékek a `docker-compose.yml`-ben vannak.

| Változó | Szolgáltatás | Mi |
|---|---|---|
| `OUR_COMPANY_NAME`, `OUR_TAX_IDS` | backend | a saját cég neve és adószámai (vesszővel), ebből dől el az irány |
| `MNB_ENDPOINT` | backend | az MNB SOAP-végpontja |
| `DATA_DIR` | backend | az SQLite helye (a képben `/data`, a Dockerfile adja) |
| `BACKEND_URL` | frontend | a backend belső címe |

- Az adatok (számlák, tárolt MNB-árfolyamok) az `invoice-data` Docker-kötetben vannak, újraindítás után is
  megmaradnak. Teljes törlés: `docker compose down -v`. A felületen az "Adatok törlése" gomb csak a számlákat
  törli, a tárolt árfolyamokat nem.
- Tesztek konténerben: `docker compose --profile test run --rm tests`

## Architektúra

```
böngésző ──> frontend (Next.js 16, TypeScript)  :8080
               └─ /api/* Route Handler proxy ──> backend (Python 3.12, FastAPI)  :8000, csak belső hálózat
                                                   ├─ extraction/  PDF -> mezők (szabályalapú)
                                                   ├─ mnb.py       MNB SOAP + tárolás + árfolyam-választás
                                                   ├─ pipeline.py  feltöltés -> kinyerés -> árfolyam -> tárolás
                                                   ├─ aggregate.py havi sor, partner-összevonás
                                                   └─ SQLite (/data/invoices.sqlite, Docker-kötet)
```

- Az üzleti logika a backendben van, a frontend csak megjelenít.
- A frontend a backendet egy futásidejű Route Handlerrel éri el (`frontend/app/api/[...path]/route.ts`),
  így kifelé egyetlen port látszik, és nincs CORS.
- A kimutatás (`/api/report`: havi sor, partnertábla, darabszám) mindig az összes számlából készül. A számlalista
  külön, lapozva jön (`/api/invoices`, 25 sor oldalanként): a keresést (`q`), a szűrőket (`direction`, határidő
  hónapja `month`, `currency`, figyelmeztetéses vagy árfolyam nélküli `flagged`), a rendezést (`sort`, `order`) és a
  lapozást az SQLite végzi. A rendezési kulcs csak egy rögzített listából jöhet. A keresés kis- és nagybetű-független
  az ékezetes betűkre is (`ulower`, Python `casefold`); a név szerinti rendezés bájtsorrendű, az ékezetes kezdőbetű a
  z után áll (magyar ábécérend nincs).
  A felület a keresőmezőt 300 ms debounce után küldi el, és az elavult kérést megszakítja.
- Minden API-válasz egy burokban jön: `{"status": "success", "message": "...", "data": {...}}`, hibánál
  `{"status": "error", "message": "..."}` a megfelelő HTTP-kóddal (`backend/app/responses.py`; a validációs, a
  404-es, a 405-ös és a váratlan hiba is magyar üzenetet kap, a belső részlet csak a naplóba kerül). A frontend
  `httpclient`-je hibánál a `message`-et felugró értesítésként írja ki (`sonner`), a komponensek a `res.data`-t
  használják.

### Projektszerkezet

```
backend/                 Python-szolgáltatás (saját Dockerfile, függőségek, tesztek)
  app/                   FastAPI-alkalmazás
    extraction/          PDF -> mezők
    mnb.py, pipeline.py, store.py, aggregate.py, main.py
  tests/                 pytest
  scripts/               fejlesztés közbeni elemző szkriptek
  Dockerfile, pyproject.toml, requirements*.txt
frontend/                Next.js-felület (saját Dockerfile)
invoices/                a 100 mintaszámla
docs/                    feladatleírás, adatfelmérés
docker-compose.yml       a két szolgáltatás és a teszt-profil
```

| Hely | Mi |
|---|---|
| `backend/app/extraction/` | `pdf_spans` (PDF -> koordinátás szöveg), `vocab` (címkeszótár), `parsing` (dátum, összeg), `taxid` (adószám), `extractor` (mezők, felek, irány, ellenőrzés) |
| `backend/app/mnb.py`, `pipeline.py`, `store.py`, `aggregate.py`, `main.py` | MNB, feldolgozás, tárolás, összesítés, API |
| `backend/tests/` | pytest; `synth.py` szintetikus PDF-eket készít, `fake_mnb.py` az MNB válaszformátumát utánozza, `samples.py` a mintaszámlák helye |
| `frontend/` | Next.js-felület: `components/`; `network/network.invoices.ts` (minden API-hívás, `networkInvoices.report()` stb.); `httpclient/httpclient.ts` (fetch, szerveren a `BACKEND_URL`, böngészőben a proxy); `app/api/[...path]/route.ts` proxy |

A mintaszámlák a repó gyökerében vannak, mert a feladat bemenetei, nem csak a backend tesztadatai. A
tesztkép a compose `additional_contexts` beállításával kapja meg őket, a backend build-kontextusa így csak a
`backend/` mappa.

### Elemző szkriptek (`backend/scripts/`)

Fejlesztés közbeni ellenőrzésre készültek, az alkalmazás nem használja őket. A `backend/` mappából futnak
(`python scripts/run_extract.py`), kimenetük a `backend/scripts/out/` mappába kerül (nincs a repóban).

- `survey.py`, `labels.py`: a mintaszámlák felmérése (oldalszám, sablon, címkék).
- `run_extract.py`: a kinyerő a 100 mintán, táblázatos kimenettel.
- `crosscheck.py`: független kontroll, a fizetési feltétel napjai és a kinyert dátumok különbsége.
- `run_rates.py`, `run_pipeline.py`: éles MNB-vel az árfolyamok, illetve a teljes folyamat kétszeri feltöltéssel.

A `run_extract.py`, `crosscheck.py`, `run_rates.py` és `run_pipeline.py` az alkalmazás kódját használja, ezért a
backend négy kötelező változója nélkül nem indul (a `survey.py` és a `labels.py` nem kéri). Bash-ben:

```bash
cd backend
export OUR_COMPANY_NAME="Nordwind Solutions Kft." OUR_TAX_IDS="26481937-2-43,HU26481937" \
       DATA_DIR=data MNB_ENDPOINT="http://www.mnb.hu/arfolyamok.asmx"
.venv/bin/python scripts/run_extract.py && .venv/bin/python scripts/crosscheck.py
```

A `crosscheck.py` és a `run_rates.py` a `run_extract.py` kimenetét olvassa, ezért előtte azt kell futtatni.

## Bemutatóhoz: hibás és szokatlan számla

- **Sérült PDF** vagy **nem PDF** (pl. átnevezett szövegfájl): a fájl "Hiba" állapotot kap, a többi feldolgozódik.
- **Idegen cég számlája** (a mi adószámunk egyik oldalon sem szerepel): "Nem dönthető el az irány" hiba.
- **Ismételt feltöltés:** "Már szerepel", ugyanaz a fájl vagy ugyanaz a számla más fájlban.
- **Szokatlan elrendezések a mintában:** kétoldalas számla a végösszeggel a 2. oldalon (PI-26-0050),
  forintos ÁFA-sor euróról szóló számlán (NW-2026-0014), lengyel "Termin płatności: 14 dni" a dátum mellett,
  kétnyelvű magyar/angol címkék.

## Az adatkinyerés működése

Részletes felmérés: [docs/adatfelmeres.md](docs/adatfelmeres.md).

1. **Szöveg koordinátákkal** (PyMuPDF): minden szövegdarab helyzettel együtt, az oldalak egymás alá fűzve, így a
   2. oldalon lévő végösszeg is megvan. Fájlnevet és sablon-azonosítót (kiállító, PDF-metaadat) nem használ.
2. **Címkeszótár** hét nyelven (HU, EN, DE, FR, ES, IT, PL), ékezet és kis-nagybetű nélküli teljes egyezéssel;
   a kétnyelvű `Magyar / English` címkét részenként vizsgálja, a zárójeles részt és a százalékot elhagyja.
3. **Érték a címkéhez:** a kettőspont után, jobbra ugyanabban a sorban, vagy alatta ugyanabban az oszlopban.
   A címkével egy vonalban, közvetlenül alatta álló érték elsőbbséget kap a távoli jobb szomszéddal szemben.
4. **Értelmezés:** dátum 8 formátumban és 7 nyelv hónapneveivel; összeg `1 234,56`, `1.234,56`, `1,234.56`,
   pénzjellel vagy kóddal. A `Termin płatności: 14 dni` nem dátum, így nem lesz fizetési határidő.
5. **Felek és irány:** a vevő-címke ("Vevő", "Bill to", "Rechnungsempfänger"...) alatti blokk a vevő; az
   eladó a többi rész cégformás (Kft., GmbH, S.r.l....) neve. Az irányt a mi adószámunk dönti el
   (26481937-2-43 / HU26481937), nem a név. Az adószámok egységes kulcsot kapnak (`14829375-2-43` = `HU14829375`).
6. **Ellenőrzés:** a végösszeg csak akkor elfogadott ellenőrzés nélkül, ha egy nettó + ÁFA = bruttó hármas
   igazolja; az erős címke ("Fizetendő", "Total due", "TOTALE DOCUMENTO") megelőzi a gyenge "Total"-t.
   Ha valamelyik kötelező mező hiányzik, vagy az irány nem dönthető el, a fájl "hiba" állapotú, nem kerül
   a kimutatásba.

**Ismeretlen formátum:** új sablon akkor működik, ha a címkéi a szótárban vannak, és az érték a címke mellett
vagy alatt áll. Ha nem, a fájl hibaüzenettel (melyik mező hiányzik) jelenik meg, nem rossz számmal.

## MNB-árfolyam

- `GetExchangeRates` SOAP-hívás (http), a feltöltött köteg összes devizájára és napjára **egyetlen** hívás,
  14 nap visszatekintéssel (hosszú ünnepnél 60 napig bővül).
- Tárolás: `mnb_rates` (nap, deviza, árfolyam, unit) és `mnb_coverage` (melyik időszakot kérdeztük le). A
  második miatt a jegyzés nélküli napot (hétvége, ünnep) sem kérdezi le újra.
- Választás: a teljesítési nap árfolyama, ha aznap nincs jegyzés, az azt megelőző utolsó; `árfolyam / unit`.
- Kerekítés: számlánként egész forintra, 0,5-től felfelé (`Decimal`, nincs lebegőpontos hiba).
- Ha az MNB nem érhető el, a számla figyelmeztetéssel tárolódik, de kimarad az összesítésből, amíg az
  "Árfolyamok újrapróbálása" gomb nem pótolja.

## Duplikáció

- Azonos fájl (SHA-256): nincs újrafeldolgozás.
- Azonos számla más fájlban: normalizált számlaszám (`DL/2026/00008` = `DL-2026-00008`) és közös kiállítói
  adóazonosító. Más kiállító azonos számlaszáma nem duplikátum.

## Tesztek

`pytest` (214 teszt): dátum-, szám-, adószám- és címke-értelmezés; regresszió a 100 mintán; szintetikus PDF-ek
a mintában nem szereplő elrendezésekkel; MNB (hétvége, ünnep, unit, kerekítés, tárolás, hívásszám, hálózati hiba);
összesítés (üres hónap, évhatár, partner-összevonás); feldolgozási folyamat (duplikáció, hibás fájl, MNB-kiesés);
számlalista (lapozás, ékezetes keresés, szűrők, rendezés); API-válaszburok (siker, 404, 405, 413, 422, 500).

Helyi futtatás Docker nélkül, a `backend/` mappából:

```bash
cd backend
python -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt   # Windowson: .venv\Scripts\pip
.venv/bin/pytest                                                    # a változókat a tests/conftest.py adja
```

A backend helyi indításához és a négy elemző szkripthez (lásd fent) a backend-változókat be kell állítani, a
frontendhez a `BACKEND_URL`-t (pl. `frontend/.env.local`-ban).

## Ismert korlátok

- A 100 mintára futó regressziós teszt elvárt értékei a saját, két független kontrollal ellenőrzött kimenetből
  készültek, nem hivatalos referenciaértékekből (ilyet a feladat nem mellékelt).
- `DD/MM/YYYY` és `MM/DD/YYYY` közül az európait feltételezi, kivéve ha a második tag 12-nél nagyobb.
- Ha a teljesítés napja ma van, és az MNB még nem tette közzé a mai jegyzést, az előző jegyzés lesz a számlán;
  ezt később nem számolja újra automatikusan.
- Szkennelt (képes) PDF-hez nincs OCR (a feladat szerint nem kell).
- Olyan sablon, amelynek címkéi nincsenek a szótárban, vagy az érték nem a címke mellett/alatt áll, "hiba"
  állapotot kap; a szótár bővítése egy sor és egy teszt.

## Miért nincs LLM

A szabályalapú kinyerés a 100 mintán minden mezőt kinyer, és minden számlán igazolja magát (nettó + ÁFA = bruttó;
a fizetési feltétel napjai egyeznek a határidő és a kiállítás különbségével). Az LLM ezen nem javítana, viszont
nem determinisztikus, pénzbe kerül, és a válaszát ugyanezekkel a szabályokkal kellene ellenőrizni. Ezért a
hibás vagy ismeretlen számla nem kerül LLM-hez: hibaüzenettel jelenik meg, és nem torzítja a kimutatást.

Továbbfejlesztési ötlet, ha a rejtett számlák között sok ismeretlen sablon lenne: LLM-tartalék csak a
"hiba" állapotú fájlokra, sémavalidációval, a nettó + ÁFA = bruttó egyezés kötelező feltételével, és annak
ellenőrzésével, hogy a visszaadott értékek szó szerint szerepelnek-e a PDF szövegében.

## AI-asszisztált fejlesztés

A folyamat: [AI_NAPLO.md](AI_NAPLO.md). Az AI-nak adott szabályok: [CLAUDE.md](CLAUDE.md).
