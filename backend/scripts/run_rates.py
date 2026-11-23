"""Éles próba: a 100 minta teljesítési napjaira MNB-árfolyam, hívásszámlálással."""
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import config, db  # noqa: E402
from app.mnb import MnbClient, RateService, to_huf  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
rows = json.loads((ROOT / "scripts" / "out" / "extract.json").read_text(encoding="utf-8"))
dbfile = ROOT / "scripts" / "out" / "rates.sqlite"
dbfile.unlink(missing_ok=True)
client = MnbClient(config.MNB_ENDPOINT)
service = RateService(db.connect(dbfile), client)
needs = [(r["cur"], date.fromisoformat(r["supply"])) for r in rows]
service.prefetch(needs)
after_prefetch = client.calls
for r in rows:
    rate = service.rate_for(r["cur"], date.fromisoformat(r["supply"]))
    r["rate"], r["rate_day"], r["huf"] = str(rate.per_unit), str(rate.day), to_huf(Decimal(r["gross"]), rate)
    if r["cur"] != "HUF" and rate.day != date.fromisoformat(r["supply"]):
        print(f'{r["file"]:30} {r["cur"]} supply={r["supply"]} ({date.fromisoformat(r["supply"]).strftime("%a")}) -> {rate.day} {rate.rate}')
print(f"MNB-hívás: prefetch után {after_prefetch}, összesen {client.calls}")
(ROOT / "scripts" / "out" / "rates.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
for r in rows:
    if r["no"] == "NW-2026-0014":
        print("kontroll NW-2026-0014:", r["supply"], r["rate"], r["rate_day"])
