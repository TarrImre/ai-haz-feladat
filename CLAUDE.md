# Számlafeldolgozó - szabályok az AI-asszisztensnek

A feladat leírása: [docs/FELADAT.md](docs/FELADAT.md) (az eredeti `FELADAT.md` a kulcs miatt nincs a repóban).

## Kötelező

- **Az OpenRouter-kulcs soha nem kerül fájlba, commitba, logba**, és a fejlesztéshez sem használjuk (a feladat tiltja).
- **Az alkalmazás nem használ LLM-et** (döntés: a szabályalapú kinyerés a mintán 100/100). Ne vezess be
  LLM-hívást; ha egy új sablon nem megy, a címkeszótárat és a szabályt bővítsd, teszttel.
- **Nincs bedrótozás a 100 mintaszámlára**: se fájlnév, se kiállító-specifikus pozíció, se ismert számlaszám a kódban.
  Rejtett, hasonló számlákkal is tesztelnek. Új sablont címkeszótár és általános szabály kezeljen.
- **Bruttó végösszeg** kell, nem nettó, nem ÁFA. **Fizetési határidő** a diagramhoz, **teljesítés dátuma** az árfolyamhoz.
- Az irány és a partner a mi cégünk adószámából dől el (26481937-2-43 / HU26481937), nem a névből.
- MNB-árfolyam: a teljesítés napja, ha nincs jegyzés, az azt megelőző utolsó; `unit`-tal osztva; számlánként egész
  forintra kerekítve (0,5 felfelé), utána összesítés. Lekért árfolyam tárolva, egy nap/deviza egyszer.

## Felépítés

- `backend/` Python FastAPI (csak `/api/*`): `app/` kinyerés, MNB, tárolás, összesítés; `tests/` pytest;
  `scripts/` elemző szkriptek. Parancsok a `backend/` mappából, a `.venv` is ott van.
- `invoices/` a mintaszámlák a gyökérben; a tesztek a `tests/samples.py` `SAMPLES_DIR`-jén át érik el.
- `frontend/` Next.js (App Router, TypeScript strict). Az `/api/*` kéréseket a `app/api/[...path]/route.ts`
  továbbítja futásidőben a `BACKEND_URL`-re; a `next.config` rewrite-ja buildkor égetné be, ezért nem azt használjuk.
- API-hívás csak a `frontend/network/` modulokon át (`networkInvoices.*`), közvetlen `fetch` nincs a komponensekben.
- Válasz mindig burokban: backend `success(data, message)`, hiba `HTTPException` (a handler `status: "error"`-ra
  alakítja). A hibát a `httpclient` írja ki felugró értesítésként és dob; a network `ApiSuccess<T>`-t ad, a
  komponens `status`-ellenőrzés nélkül a `data`-t használja, és a hibát nem írja ki újra.
- Konfiguráció csak kötelező környezeti változóból (`config.py` `_require`, `lib/env.ts` `requireEnv`), beégetett
  alapérték (`?? "..."`, `os.getenv(x, "...")`) nincs; az értékek a `docker-compose.yml`-ben.
- Üzleti logika csak a backendben; a frontend megjelenít, nem számol újra összeget.

## Munkamód

- Kis, beszédes commitok, lépésenként; minden meghatározó döntés és AI-tévedés az `AI_NAPLO.md`-be.
- Állítás csak ellenőrzött adatból (a PDF tényleges szövege, teszt, MNB-válasz), nem feltételezésből.
- Új kinyerési szabály mellé teszt; a 100 mintán futó regressziós összevetés minden kinyerő-módosítás után.
- Kódkomment egy sor, pár szó. Csak sima kötőjel (`-`), en/em dash sehol.
