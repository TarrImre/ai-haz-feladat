"""Éles próba: a 100 minta kétszer feltöltve, havi sor és partnertábla kiírva."""
import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import aggregate, config, db, store  # noqa: E402
from app.mnb import MnbClient, RateService  # noqa: E402
from app.pipeline import process_files  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
dbfile = ROOT / "scripts" / "out" / "pipeline.sqlite"
for suffix in ("", "-wal", "-shm"):
    Path(str(dbfile) + suffix).unlink(missing_ok=True)
conn = db.connect(dbfile)
client = MnbClient(config.MNB_ENDPOINT)
service = RateService(conn, client)
files = [(p.name, p.read_bytes()) for p in sorted((ROOT.parent / "invoices").glob("*.pdf"))]
first = process_files(conn, service, files)
second = process_files(conn, service, files)
print("1. feltöltés:", collections.Counter(r.status for r in first))
print("2. feltöltés:", collections.Counter(r.status for r in second))
print("MNB-hívás:", client.calls, " tárolt számla:", len(store.all_invoices(conn)))
facts = store.facts(store.all_invoices(conn))
print("\nHónap      Bejövő        Kimenő")
for m in aggregate.monthly(facts):
    print(f"{m.month}  {m.incoming:>12,}  {m.outgoing:>12,}".replace(",", " "))
print("\nPartner                              Bejövő        Kimenő   adószámok")
for c in aggregate.partners(facts):
    print(f"{c.name[:34]:34} {c.incoming:>12,}  {c.outgoing:>12,}".replace(",", " ") + f"   {c.tax_ids}")
tot_in = sum(f.huf_total for f in facts if f.direction == "bejovo")
tot_out = sum(f.huf_total for f in facts if f.direction == "kimeno")
print(f"\nÖsszesen bejövő {tot_in:,}  kimenő {tot_out:,}")
