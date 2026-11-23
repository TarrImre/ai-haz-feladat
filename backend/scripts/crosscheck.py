"""Független kontroll: a fizetési feltétel napjai és a kinyert dátumok különbsége."""
import json
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.extraction.pdf_spans import full_text, load_spans  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
TERMS = re.compile(r"(?i)(\d{1,3})\s*(nap|days?|tage|jours|d[ií]as|giorni|dni)\b")
rows = json.loads((ROOT / "scripts" / "out" / "extract.json").read_text(encoding="utf-8"))
bad = 0
for r in rows:
    text = full_text(load_spans((ROOT.parent / "invoices" / r["file"]).read_bytes()))
    terms = {int(m.group(1)) for m in TERMS.finditer(text)}
    issue, supply, due = (date.fromisoformat(r[k]) for k in ("issue", "supply", "due"))
    d_issue, d_supply = (due - issue).days, (due - supply).days
    ok = d_issue in terms or d_supply in terms
    if not ok:
        bad += 1
        print(f'{r["file"]:30} terms={sorted(terms)} due-issue={d_issue} due-supply={d_supply} {r["issue"]} {r["supply"]} {r["due"]}')
print(f"eltérés: {bad}/{len(rows)}")
