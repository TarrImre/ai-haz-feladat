# AI-napló

Eszköz: Claude Code (VS Code-bővítmény), modell: Claude Opus 5.5.
Szabályfájlok: [CLAUDE.md](CLAUDE.md) (repó-szintű), valamint a saját, projektfüggetlen globális szabályaim
(magyar kommunikáció, egysoros komment, "előbb tény, utána kód", ellenőrzött/nem ellenőrzött jelentés).
A beszélgetés exportja: [ai-logs/](ai-logs/).

## Összefoglaló

**Hogyan irányítottam:** minden lépés előtt az AI javaslatot tett, én döntöttem (lépésbontás, Python + FastAPI,
szabályalapú kinyerés, Next.js csak felületnek, LLM nélkül). Minden lépés után a "kész" állítást mérés
igazolta: teszt, éles futás a 100 mintán, független kontroll, böngészős teszt konzol-figyeléssel.

**Ahol az AI tévedett, és mi fogta meg:**

| Tévedés | Mi fogta meg |
|---|---|
| BillFlow: a teljesítés dátuma helyett a szomszéd oszlop határideje | a kimeneti táblázat feltűnő ismétlődése (supply == due) |
| "ÁFA összesen (27%)" címke a zárójel miatt nem egyezett | a nettó + ÁFA = bruttó ellenőrzés 90 fájlon elbukott |
| Olasz tételtábla fejléce hamis, de konzisztens végösszeget adott | regressziós teszt a 100 mintán |
| A szintetikus teszt-PDF betűje nem tudta az "ő", "€" jelet | két hamisan bukó teszt; a tesztkészítő hibája volt, nem a kinyerőé |
| Mai napra (még nincs MNB-jegyzés) végtelen újrakérdezés | dedikált egységteszt |
| Az upload-napló üres hash-sel írt | kódolvasás, utána teszt |
| `.pdf` nevű szövegfájlt a PDF-olvasó elfogadott | böngészős próba, kézzel feltöltött rossz fájllal |
| Hibás fájl miatt a 101 soros lista lenyomta a diagramot; tagolatlan "5465,00" | képernyőképek 1440 és 390 px-en |
| A `.env.example` nem létező LLM-funkciót írt le | átnézés a "csak azt írd, amit a kód csinál" szabállyal |
| Szóközös számlaszámból (`PT 2026 1`) csendben `2026` lett, "rendben" állapottal | végponti teszt szélsőséges szintetikus számlákkal |
| Csonka PDF-re "szkennelt kép?" üzenet | ugyanez a végponti teszt, az üzenetek kiírásával |
| A szándékosan megszüntetett `.env.example` visszahozását javasolta | a napló 14. lépésének utólagos olvasása |

**Ahol nem bíztam meg az AI eredményében:** a "100/100 ok" csak belső összhangot jelentett, ezért kértem
független kontrollt (fizetési feltétel vs. dátumok; a számlára nyomtatott MNB-árfolyam vs. az MNB-válasz).
A regressziós teszt elvárt értékei a saját, ellenőrzött kimenetből készültek, nem hivatalos referenciából;
ezt a README is kimondja.

## 1. Feladatbontás (2026-11-23)

**Prompt:** "Bontsuk részekre, mivel kezdenéd?"

**AI javaslata:** 0. repó-alap, 1. adatfelmérés (a 100 PDF szövege, sablonok), 2. kinyerési döntés,
3. kinyerő + tesztek, 4. MNB-modul, 5. aggregálás, 6. web-UI, 7. Docker, 8. LLM-tartalék, 9. dokumentáció.

**Döntés:** elfogadva. Az indok: a kinyerési módot (szabályalapú vagy LLM) csak a PDF-ek tényleges szövege
alapján lehet eldönteni, ezért az adatfelmérés megelőzi a technológia- és architektúra-döntést.

## 2. Repó-alap (2026-11-23)

- A feladatleírás (`FELADAT.md`) szó szerint tartalmazza az OpenRouter-kulcsot. Az eredeti fájl `.gitignore`-ba
  került, a repóban a kulcs nélküli másolat van: [docs/FELADAT.md](docs/FELADAT.md).
- `CLAUDE.md`: a feladat csapdái szabályként (bruttó vs. nettó, három dátum szerepe, irány adószámból, nincs
  bedrótozás, a kulcs fejlesztéshez nem használható).

## 3. Adatfelmérés (2026-11-23)

**Prompt:** "mehet a 0 és az 1. lépés"

**Mit csinált az AI:** szövegkinyerés `pdftotext -layout`-tal, majd a PyMuPDF span-szintű kimenetével; címke-szótár
sablononként; dátum- és számformátumok számlálása; duplikátum-keresés; az MNB-szolgáltatás próbahívása.
Eredmény: [docs/adatfelmeres.md](docs/adatfelmeres.md).

**Észrevételek, amelyek a döntést befolyásolják:**
- A `-layout` szöveg több sablonnál összecsúszik ("Tota8l d5u4e5,00"). Ha erre építünk, a regex-alapú kinyerés
  törékeny lesz; a koordinátás span-ek tiszták. Ezért a kinyerés span-alapú, címke-érték párosítással.
- Az AI első címkekeresése a saját kimeneti fájlját (`labels.txt`) is beolvasta a grep-be, ezért zajos lett az
  eredmény. Észrevettem, a mintát leszűkítettem.
- A számlára nyomtatott árfolyam és az MNB-válasz egyezése független kontrollt adott a "teljesítési nap" szabályra.

## 4. Kinyerési döntés és a kinyerő (2026-11-23)

**Prompt:** "igen mehet tovább a második lépés" (Python + FastAPI + SQLite jóváhagyva)

**Döntés:** szabályalapú kinyerés, LLM csak tartalék (később). Indok: a feladat ezt előnynek nevezi, a kulcs keretes,
és a span-alapú címke-érték párosítás a felmérés szerint mind az öt sablonon működik. A sablon felismerését
(PDF `creator`, kiállító neve) szándékosan nem használjuk, mert a rejtett számlák más sablonból jöhetnek.

**Felépítés:** `pdf_spans` (koordinátás szöveg, az oldalak egymás alá fűzve) -> `vocab` (7 nyelvű címkeszótár,
ékezet nélküli teljes egyezés, kétnyelvű `A / B` címkék) -> `extractor` (érték a címke után, jobbra vagy alatta;
partner-blokk a vevő-címke alatt; irány a mi adószámunkból) -> ellenőrzés (nettó + ÁFA = bruttó, kötelező mezők).

**Hol tévedett az első változat, és hogyan derült ki:**
1. A BillFlow-sablonon a teljesítés dátuma mindig a határidővel egyezett, mert a "jobbra az első span" a
   szomszéd oszlop értékét vette. Észrevétel: a kimeneti táblázatban supply == due feltűnő ismétlődése. Javítás: a
   címke alatt, vele egy vonalban kezdődő érték elsőbbséget kap. Ellenőrzés: a 33 kétértelmű esetet
   listáztam, mind BillFlow, és kettőt koordinátákkal kézzel is megnéztem.
2. A nettó + ÁFA = bruttó ellenőrzés 90 fájlon elbukott, mert az "ÁFA összesen (27%)" címkét a zárójel miatt
   nem ismerte fel. Javítás: zárójeles rész és százalék eltávolítása a címkéből.
3. A "Total" és "Totale" általános címke felvétele után az olasz számlákon a tételtábla fejlécéből (Totale,
   Imponibile, Imposta) is kijött egy hibás, de belsőleg konzisztens hármas (2211 a 2744 helyett). **A
   regressziós teszt fogta meg.** Javítás: gyenge címke csak erős címke hiányában, és a legnagyobb végösszeg nyer.
4. A szintetikus teszt-PDF-ekben a Base14 betű nem tudta az "ő", "ű", "€" karaktert, ezért két teszt hamisan
   bukott el. Ez a tesztkészítő hibája volt, nem a kinyerőé; HTML-szövegdobozra cseréltem (Unicode-betű).

**Független kontrollok:** a határidő - kiállítás (vagy - teljesítés) napjainak száma mind a 100 számlán egyezik a
számlára írt fizetési feltétellel (`analysis/crosscheck.py`).

**Tesztek:** egységtesztek (dátum, szám, adószám, címke), regresszió a 100 mintán (az ellenőrzött kimenetből,
nem hivatalos referencia), szintetikus PDF-ek a mintában nem szereplő címkékkel és elrendezéssel (egymás melletti
eladó/vevő blokk, egymás alatti fejléc-sor, végösszeg a 2. oldalon, forintos ÁFA-sor deviza-számlán, hibás PDF).

## 5. MNB-árfolyam modul (2026-11-23)

**Prompt:** "igen mehet a 4. lépés"

**Döntések:**
- Tárolás SQLite-ban két táblával: `mnb_rates` (nap, deviza, árfolyam, unit) és `mnb_coverage` (melyik időszakot
  kérdeztük le devizánként). A második azért kell, mert a hétvége és az ünnep nem szerepel a válaszban; csak az
  árfolyam-táblából nem derülne ki, hogy egy napot már lekérdeztünk, és újra kérnénk.
- Kötegelt lekérés: a feltöltött számlák összes devizájára és napjára egy hívás, 14 nap visszatekintéssel; ha
  ez sem elég (hosszú ünnep), a visszatekintés duplázódik 60 napig.
- Az árfolyam `rate / unit`, a kerekítés számlánként `ROUND_HALF_UP` egész forintra, `Decimal`-lal (nincs float).

**Hol tévedett az AI:** az első változat a mai napra (amire az MNB még nem tett közzé jegyzést) végtelen
újrakérdezésbe, majd hibába futott volna. A `test_today_without_quote_is_not_cached_as_covered` teszt fogta meg.
Javítás: friss lekérés után a legutóbbi közzétett jegyzés érvényes, de a mai nap nem számít lefedettnek, így a
később megjelenő jegyzést még lekéri.

**Éles ellenőrzés:** a 100 minta teljesítési napjaira 1 MNB-hívás kellett. A 16 hétvégi/ünnepi esetet kilistáztam
(pl. 2026-10-25 vasárnap -> 10-22 csütörtök, mert 10-23 ünnep), és az NW-2026-0014-re nyomtatott 396,92 egyezik.

## 6. Adatmodell, duplikáció, összesítés (2026-11-23)

**Prompt:** "igen csináld" (5. lépés)

**Döntések:**
- Két szintű duplikáció-szűrés. (1) Azonos fájl (SHA-256): nincs újra-kinyerés, így később LLM-hívás sem.
  (2) Azonos számla más fájlban: normalizált számlaszám (`DL/2026/00008` = `DL-2026-00008`) + közös kiállítói
  adóazonosító (adószám nélkül a normalizált név). Más kiállító azonos számlaszáma nem duplikátum.
- A partner nem tábla, hanem lekérdezéskori összevonás (unió-keresés) a számlák partner-adóazonosítóin és
  normalizált nevén. Így ha egy számla összeköt két azonosítót (pl. `FR47829461375` és a SIRET), a többi számla
  is ugyanahhoz a céghez kerül. Megjelenített név: a nem csupa nagybetűs írásmód.
- Az összesítő modul (`aggregate.py`) tiszta függvény, adatbázis nélkül tesztelhető.
- Árfolyam nélkül (MNB nem elérhető) a számla tárolódik, figyelmeztetéssel, de kimarad az összesítésből, amíg a
  `retry_missing_rates` pótolja.

**Hol tévedett az AI:** az upload-naplóba üres hash került (a `FileResult` nem vitte tovább); kódolvasáskor vettem
észre, és a `test_bad_file_does_not_stop_batch` most a naplót is ellenőrzi. A megjelenített partnernév a
gyakoriság miatt csupa nagybetűs lett ("DUNA LOGISZTIKA ZRT."); az éles futás kimenetéből tűnt fel.

**Éles ellenőrzés (`analysis/run_pipeline.py`):** a 100 minta 1. feltöltése 100 ok, a 2. feltöltése 100
duplikált, 1 MNB-hívás, 12 partner. A havi sor és a partnertábla bejövő összege egyezik (49 743 804 Ft).

## 7. Webes felület: Next.js + TypeScript (2026-11-23)

**Prompt:** "csináld igen", majd munka közben: "egy nextjs appot szeretnék ts-sel"

**Irányváltás:** az AI először egy statikus HTML/JS felületet kezdett írni a FastAPI-ba. A Next.js-kérésre nem
kezdett átírásba, hanem rákérdezett, mire vonatkozzon: (1) csak a felület, a Python marad API-ként; (2) teljes
átírás TS-re; (3) Next.js BFF + Python worker. **Döntésem: (1).** Indok: a kinyerés, az MNB és az összesítés
183 teszttel és a 100 mintán igazolva van; a teljes átírás ezt mind újra-igazoltatná, előny nélkül.

**Felépítés:** `frontend/` (Next.js 16, App Router, TS strict, `noUncheckedIndexedAccess`), react-chartjs-2.
A kezdőlap szerveroldalon kéri le a kimutatást (nincs üres villanás), a feltöltés kliensoldali, 10 fájlos
csomagokban, folyamatjelzővel. A `/api/*` proxy egy Route Handler, mert a `next.config` rewrite a
standalone buildbe égetné a backend címét (Dockerben más a cím, mint helyben).

**Böngészős teszt (Playwright, Chrome, konzol-figyeléssel), és amit talált:**
- A teljes 100-as csomag + 1 sérült PDF: 100 rendben, 1 hiba; ismételt feltöltés: "Már szerepel"; keresés
  szűr; frissítés után megmarad; 390 px-en nincs vízszintes görgetés.
- Egy `.pdf` nevű szövegfájlt a PyMuPDF szöveges dokumentumként megnyitott, és "hiányzó mezők" hibát adott.
  Javítás: `%PDF-` fejléc nélkül azonnal "Nem PDF-fájl"; teszt hozzáadva.
- A képernyőképeken: egyetlen hibás fájl miatt a 101 soros eredménylista nyitva maradt, és a diagram messze
  lecsúszott (most csak a hibás sorok látszanak, a teljes lista összecsukva); a dátumok tördelődtek; a hu-HU
  formátum a négyjegyű számot nem tagolja ("5465,00" a "21 545,00" mellett), ezért `useGrouping: "always"`;
  a simított görbe a hónapok között nem létező értéket sugallt, ezért egyenes szakaszok.
- Konzolhiba: favicon 404, saját ikon került be. A régi `next start` a leállítás után is fogta a portot
  (a háttérfolyamat csak az `npx` szülőt állította le); folyamat-azonosítóval ellenőrizve állítottam le.

## 8. Docker (2026-11-23)

**Prompt:** "csináld" (7. lépés)

**Felépítés:** két image. Backend: `python:3.12-slim`, nem root felhasználó, healthcheck, `/data` kötet. A
`test` build-stage ugyanabból az alapból a teszteket és a mintákat is tartalmazza (`--profile test`).
Frontend: `node:22-alpine` többlépcsős build, Next.js `standalone` kimenet. A frontend csak a backend
`service_healthy` állapota után indul. A `.env` opcionális (`required: false`), kulcs nélkül is elindul.

**Ellenőrzés:** `docker compose build` + `up`: a böngészős teszt a 8080-as porton ugyanazt adja, mint helyben
(100 rendben + 1 hiba, ismételt feltöltés "Már szerepel", konzol hibamentes). `down` + `up` után a 100 számla
megmaradt (kötet). A 184 teszt a konténerben is zöld.

**Az AI pontosítása:** a `.env.example` első változata leírta az LLM-tartalékot, ami még nem létezik; a
"csak azt írd, amit a kód csinál" szabály alapján átírtam ("még nincs bekötve").

## 9. LLM: nem kell (2026-11-23)

**Prompt:** "Nem kell az llm ha nincs rá szükség"

**AI javaslata:** két lehetőség, (a) LLM-tartalék csak a szabályalapon elbukó fájlokra, sémavalidációval és
nettó + ÁFA = bruttó feltétellel; (b) kihagyás indoklással.

**Döntés: (b).** A mintán a szabályalapú kinyerés 100/100, két független kontrollal igazolva. Az LLM nem
determinisztikus, keretes kulcsot fogyaszt, és a válaszát ugyanazokkal a szabályokkal kellene ellenőrizni.
Az ismeretlen számla hibaként jelenik meg, nem torzítja a kimutatást. A feleslegessé vált OpenRouter-
beállítások kikerültek a configból és a `.env.example`-ből; a `CLAUDE.md` most tiltja az LLM bevezetését.
A (a) változat továbbfejlesztési ötletként a README-be került.

## 10. Lezárás (2026-11-23)

**Prompt:** "csináld" (9. lépés)

- Tiszta indítási próba: `docker compose down -v`, `build --no-cache`, `up`. Üres adatbázissal indul; a
  böngészős teszt (100 számla + 1 sérült PDF, ismételt feltöltés, keresés, frissítés, 390 px) zöld, konzol
  hibamentes. A Dockerben kapott összegek egyeznek a helyi futáséval (bejövő 49 743 804 Ft, kimenő
  171 702 991 Ft; a havi sor és a partnertábla összege is egyezik).
- README: projektszerkezet, az elemző szkriptek leírása, bemutatóhoz a hibás és szokatlan számlák.
- Az AI az `ai-logs/README.md` első változatában azt írta, hogy a kulcsot "eltávolítottam" az exportból, holott
  export még nem volt; teendőként fogalmaztam át.

## 11. Felület-átdolgozás, szerveroldali lapozás (2026-11-23)

**Prompt:** "csináld meg ezt a ui-t hogy ne ilyen ai slop legyen", majd "a betűtípus nagyon ai", "legyen
pagination", "oldalanként fetchelje és a kereső is működjön fetchként".

- **Kinézet:** az AI nem egy saját változatot írt be, hanem egy demóoldalt adott három eltérő elrendezéssel
  (főkönyv, nagy tipográfia, munkaeszköz) a valódi adatokkal. Választás: a sötét oldalsávos munkaeszköz. A
  betűre külön demó hat párral; választás: Public Sans (`next/font`, `latin-ext` az ő, ű miatt).
- **AI-tévedések, mérés fogta meg:** (1) a számjegy-szélesség mérése mind a hat betűnél 280 px-et adott, mert
  a mérőelem rácselemként a 280 px-es oszlopra nyúlt; abszolút pozícióval mérve derült ki, hogy a Libre
  Franklin Google-változatában nincs táblázatos számjegy, ezért kiesett. (2) "Kész"-nek mondta, de a 8080-on
  a régi felület futott: a Docker-image a módosítás előtt épült (image-idő és fájlidő összevetése). (3) A
  lapozó 4 oldalnál "1 2 … 4"-et mutatott, a "…" egyetlen oldalt takart.
- **Lapozás:** előbb kliensoldali (a riport amúgy is minden számlát hozott). Kérésre szerveroldali lett:
  `GET /api/invoices` (SQLite `LIMIT/OFFSET`, `COUNT`, a túl nagy oldalszám az utolsóra esik, `page_size`
  legfeljebb 100). A `/api/report` a számlalista helyett csak a darabszámot adja; a diagram és a partnertábla
  továbbra is minden számlából számol. Az SQLite `LOWER()` csak ASCII-t kisbetűsít, ezért saját `ulower`
  függvény (Python `casefold`); a `%` és `_` a keresésben szó szerinti. 7 új teszt (191).
- **Böngészős ellenőrzés (Playwright, a kérések naplózásával):** betöltéskor 0 számlalista-kérés (az első oldal
  szerveroldalon jön), lapozásonként 1 kérés, a "könyvelő" 60 ms-onként begépelve 1 kérés (debounce 300 ms).
- **Rendezés és szűrők** ("csináld mindet"): oszlopfejlécre kattintva rendez (Számlaszám, Kiállító, Vevő, a három
  dátum, Bruttó HUF; a hiányzó forintösszeg mindig a végére kerül), szűrő a határidő hónapjára, a pénznemre és a
  figyelmeztetéses vagy árfolyam nélküli számlákra. Az AI eredetileg "Partner" szerinti rendezést javasolt, de a
  táblában nincs Partner oszlop, ezért Kiállító és Vevő lett. A figyelmeztetés-szűrő a 100 mintán 0 találatot ad
  (nincs figyelmeztetés, minden árfolyam megvan), ezt csak a teszt igazolja. 6 új teszt (197).
- **Finomítások a képernyőképek alapján:** a keresőmező helyőrzője nem fért ki (mérve: 205 px szöveg, 186 px hely);
  a rendezés jele SVG lett, a nagybetűk közepére mérve (pixelmérés, az első mérés a halvány felét kihagyta);
  egyforma legördülők saját nyíllal, egyforma szélességű irány-jelvények; becsukható oldalsáv (az állapot a
  böngészőben marad). A legördülő lista áttűnése a Windows natív menüjéé, CSS-sel nem kapcsolható ki, ezért a
  lista `appearance: base-select`-tel az oldalon rajzolódik (Chrome, Edge); más böngészőben a natív lista marad.

## 12. Teljes teszt minden esetre, és a talált hibák javítása (2026-11-23)

- **Kérés:** "futtass egy teljes tesztet az egész projekten", utána "amilyen hibát találsz, javítsd".
- **Rétegek:** pytest helyben és konténerben; `tsc`; API-teszt a futó Docker-stacken a Next.js-proxyn át (hibás,
  üres, csonka, jelszavas, szkennelt, idegen, 20 MB feletti fájl, 201 fájl, útvonalas és ékezetes fájlnév,
  duplikáció négyféleképpen, 4 párhuzamos azonos feltöltés, hétvégi EUR- és unit=100 JPY-számla az MNB-től
  függetlenül lekért árfolyammal, összegek egyeztetése, lapozás, szűrők, rendezés, 8 hibás paraméter, SQL-injekció);
  MNB-kiesés elérhetetlen végponttal, majd újrapróbálás; újraindítás és leállított backend; böngészős teszt
  (feltöltés, lapozás, keresés, szűrők, rendezés, oldalsáv, törlés Mégse/OK, 390-1440 px, konzol).
- **Két hiba, mindkettő az AI kódjában:** (1) a számlaszám-regex a szóköznél megállt, így `PT 2026 1` helyett
  `2026` lett a számlaszám, hibajelzés nélkül. Javítás: ha az érték minden tagja számlaszám-darab (rövid nagybetűs
  előtag vagy számjegyes tag) és egyik sem dátum, az egész érték a számlaszám; különben a régi szabály. A 100 minta
  értékei mind egy tagúak, a regresszió nem változott. (2) Csonka PDF-re "szkennelt kép?" volt az üzenet; a MuPDF
  `is_repaired` jelzője az ép mintákon hamis, a csonkán igaz, ezzel szétválik a két eset.
- **A tesztelő saját hibája:** a böngészős rendezés-ellenőrzés elsőre bukott, mert a selector a pivottábla sorait is
  beszámolta; a selector szűkítése után zöld. Ez nem az alkalmazás hibája volt.
- **Eredmény:** 203 pytest (6 új), API-teszt 89/89, MNB-kiesés 8/8, böngészős teszt 47/47.

## 13. Mappaszerkezet: a backend a saját mappájába (2026-11-23)

- **Kérés:** a backend legyen külön mappában, mint a frontend, az ipari szokás szerint.
- **Döntés:** `backend/` (`app/`, `tests/`, `scripts/`, `Dockerfile`, `pyproject.toml`, `requirements*.txt`,
  `.dockerignore`), `git mv`-vel, hogy az előzmények megmaradjanak. Az `analysis/` neve `backend/scripts/` lett. A
  Python-importok (`app.*`) nem változtak, mert a gyökér a `backend/` lett.
- **A mintaszámlák a gyökérben maradtak**, mert a feladat bemenetei. A tesztek a `tests/samples.py` `SAMPLES_DIR`-jén
  át érik el őket (helyben a repó gyökeréből, a tesztképben `/invoices`); a tesztkép a compose
  `additional_contexts` beállításával kapja meg őket, így a backend build-kontextusa csak a `backend/` mappa.
- **Ellenőrzés:** 203 pytest helyben (új `backend/.venv`) és konténerben; `run_extract.py` és `crosscheck.py` az új
  helyről (eltérés 0/100); `docker compose up -d --force-recreate` után a felület és az `/api/health` 200.

## 14. Kötelező környezeti változók, network réteg a frontendben (2026-11-23)

- **Kérés:** a beégetett alapértékek (`process.env.BACKEND_URL ?? "http://localhost:8000"`, `os.getenv(x, "...")`)
  helyett hiányzó változónál hiba; az API-hívások egy network rétegen át, a user másik projektjének mintájára
  (`httpclient/` + `network/network.<terület>.ts`, `networkX = { ... }`).
- **Backend:** a `config.py` minden változót kötelezőnek vesz (`_require`), hiányzónál az indítás `RuntimeError`-ral
  leáll. A `DB_PATH` megszűnt, mindig `DATA_DIR/invoices.sqlite`. Az értékek a `docker-compose.yml`
  `environment:` részében vannak, így továbbra is egy paranccsal indul; a `.env` és a `.env.example` megszűnt,
  mert semmi nem olvasta volna. A teszteknek a `tests/conftest.py` adja az értékeket.
- **Frontend:** `lib/env.ts` `requireEnv`; `httpclient/httpclient.ts` (szerveren a `BACKEND_URL`, böngészőben a
  relatív proxy-út); `network/network.invoices.ts` (`report`, `list`, `upload`, `retryRates`, `reset`), a
  `lib/api.ts` helyett. A `page.tsx` is ezen megy. Csapda: a `page.tsx` a backend kiesését `.catch(() => null)`-lal
  kezeli, ami a hiányzó változó hibáját is elnyelné; ezért a cím feloldása szinkron, a promise előtt dob.
- **Ellenőrzés:** 203 pytest helyben és konténerben; változó nélkül a backend `RuntimeError`-t, a frontend-konténer
  500-at és "Hiányzó környezeti változó: BACKEND_URL" naplót ad; a stack 200; a szerveren renderelt oldalban
  benne vannak a számlák; böngészős próba (betöltés, keresés, lapozás, feltöltés) konzolhiba nélkül.

## 15. Egységes válaszburok és felugró hibaüzenet (2026-11-23)

- **Kérés:** a szerver és a network réteg úgy beszéljen, mint a user másik projektjében: burok (`status`, `message`,
  `data`), a hibát a httpclient írja ki felugró értesítésként.
- **Backend:** `app/responses.py`: `success(data, message)` minden végponton; exception handlerek a `HTTPException`-re
  (a keretrendszer angol 404/405-üzenete helyett magyar), a validációs hibára (422, a hibás mezők nevével) és minden
  más kivételre (500, általános üzenet, a részlet csak a naplóba). A fájlonkénti feldolgozási hiba marad a
  `data.results`-ban, mert a kérés sikeres. 9 új API-teszt (212).
- **Frontend:** `network/network.types.ts` `ApiResponse<T>` diszkriminált unió; a `httpclient` hibánál `toast.error`-t
  ad (`sonner`, csak böngészőben), és dob; megszakított kérésnél nem szól. A komponensek a `res.data`-t használják,
  a saját hibaszövegük megszűnt (kétszer jelent volna meg); csak a szerveroldali első betöltés sávja maradt, mert ott
  nincs értesítés. A proxy 502-je is burokban jön.
- **Elvetve:** az egy végpontos, `action` mezős hívás (mint ott a `manage.php`); itt a REST-útvonalak maradtak. A
  feltöltés XHR-es bájt-százaléka sem kellett: a meglévő sáv a feldolgozott fájlokat számolja, és az idő a
  feldolgozáson megy el, nem a feltöltésen.
- **Ellenőrzés:** 212 pytest helyben és konténerben; `tsc`; curl a proxyn át (siker, 422, 404 burokban); böngészős
  próba: betöltés, keresés, duplikált feltöltés (nincs értesítés), szimulált 500 és hálózati hiba (értesítés
  megjelenik, a lista megmarad), képernyőkép 1440 px-en.
- **Utána:** a komponensekben a `res.status === "success"` ellenőrzés felesleges volt, mert a httpclient hibánál
  dob. A httpclient és a network most `ApiSuccess<T>`-t ad vissza (csak a sikeres ág), a komponens közvetlenül a
  `data`-t használja (`const { data } = await networkInvoices.upload(part)`). Ebben eltér a mintaprojekttől.

## 16. Átnézés: az elemző szkriptek a kötelező változók óta nem indultak (2026-11-23)

- **AI-tévedés:** a 14. lépésben a README csak a két MNB-s szkriptnél írta, hogy változó kell, de a `run_extract.py`
  és a `crosscheck.py` is az `app`-ot importálja. A teljes átnézéskor a `crosscheck.py` "0/100"-at írt, de a
  `run_extract.py` előtte hibával leállt, így a kontroll a régi kimenetet olvasta. A kilépési kód nézése fogta meg.
- **Javítás:** README: melyik négy szkript kéri a változókat, egy kipróbált parancssor hozzá; a `survey.py` és a
  `labels.py` nem kéri. Beállítófájl nem lett a szkripteknek, mert az is beégetett érték lenne.
- **Ellenőrzés:** a README parancsaival friss futás: 100/100, a kontroll 0/100 eltérés; a két másik szkript
  változók nélkül is lefut.

## 17. Átnézés: beégetett cégadat a felületen (2026-11-23)

- **Hiba:** a `Dashboard.tsx` oldalsávja kézzel írta ki a cégnevet és az adószámot, holott ezek a backend kötelező
  változói (`OUR_COMPANY_NAME`, `OUR_TAX_IDS`); két helyen kellett volna karbantartani.
- **Javítás:** a `/api/report` `company` mezőt ad (`name`, az első adóazonosító), a felület ezt írja ki; ha a
  backend nem érhető el, a sor nem jelenik meg. 1 új API-teszt (213).
- **Apróságok ugyanebből az átnézésből:** az árfolyam-újrapróbálás eredménye `alert()` helyett `toast.success`; a
  feltöltés az első hibás adag után leáll (a többi fájl "nem lett feltöltve" sort kap), így egy értesítés jön, nem
  adagonként egy; a `/api/report` nyers SQL-je a `store.failed_uploads`-ba került, teszttel (214). A README
  előfeltétele kimondja, hogy az első buildhez internet kell; a betű helyi tárolása ezen nem változtatna, mert a
  pip és az npm is a hálózatról tölt.
- **Ellenőrzés:** 214 pytest; `tsc`.

## 18. Leadás előtti átnézés: git history és `.env.example` (2026-11-23)

- **Kérés:** "commitoltam, nézd meg hogy minden rendben van e".
- **Átnézés:** a kulcs a teljes historyban sehol (keresés a valódi kulcsra); 214 pytest; `tsc`; a leadandók a
  feladatleírás szerint. Fő hiba: a munka egyetlen "first commit"-ban került fel, a feladat szerint ez nem elfogadható.
- **A history utólagos bontása:** a fejlesztés közben nem commitoltam lépésenként, ezt pótoltuk. A végleges fájlok
  kilenc commitba kerültek, a napló lépéseinek sorrendjében (repó-alap, adatfelmérés, kinyerő, MNB, tárolás és
  összesítés, API, felület, Docker, dokumentáció), utána force-push. A commitok a végső kódot tartalmazzák, nem a
  köztes állapotokat, ezért nem mind futtathatók önmagukban, és a dátumuk a bontás napja. Ellenőrzés: a régi és az
  új végső fa közti különbség csak az új `.env.example`; 214 pytest.
- **AI-tévedés:** a `.env.example` visszahozását az AI "hiányzik, a feladat kéri" alapon javasolta, holott a 14.
  lépésben szándékosan szűnt meg, mert semmi nem olvasta. A napló utólagos olvasása fogta meg. Megtartottuk: a
  feladat kéri, és most csak azt mondja ki, hogy kulcs nem kell, a beállítások a `docker-compose.yml`-ben vannak.
