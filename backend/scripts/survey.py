"""Adatfelmérés: oldalszám, metaadat, első sorok, kulcs-címkék a mintaszámlákból."""
import json
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "scripts" / "out"

rows = []
for pdf in sorted((ROOT.parent / "invoices").glob("*.pdf")):
    doc = fitz.open(pdf)
    text = "\n".join(page.get_text() for page in doc)
    first = [ln.strip() for ln in text.splitlines() if ln.strip()][:6]
    rows.append({
        "file": pdf.name,
        "pages": doc.page_count,
        "producer": doc.metadata.get("producer"),
        "creator": doc.metadata.get("creator"),
        "title": doc.metadata.get("title"),
        "author": doc.metadata.get("author"),
        "chars": len(text),
        "first": first,
        "has_our_tax": bool(re.search(r"26481937", text)),
    })

(OUT / "survey.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
sys.stdout.reconfigure(encoding="utf-8")
for r in rows:
    print(f'{r["file"]:34} p{r["pages"]} {r["producer"]!s:28.28} {r["creator"]!s:20.20} | {" / ".join(r["first"][:3])[:90]}')
