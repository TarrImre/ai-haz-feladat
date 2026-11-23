"""Címke-szótár felmérése: minden ':'-ra végződő vagy félkövér span, sablononként számolva."""
import collections
import re
import sys
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")

labels = collections.Counter()
odd = []
for pdf in sorted((ROOT.parent / "invoices").glob("*.pdf")):
    doc = fitz.open(pdf)
    creator = doc.metadata.get("creator")
    for pno, page in enumerate(doc):
        w, h = page.rect.width, page.rect.height
        for b in page.get_text("dict")["blocks"]:
            for line in b.get("lines", []):
                for s in line["spans"]:
                    t = s["text"].strip()
                    if not t:
                        continue
                    x0, y0, x1, y1 = s["bbox"]
                    if s["size"] < 5 or x1 < 0 or y1 < 0 or x0 > w or y0 > h:
                        odd.append((pdf.name, pno, round(s["size"], 1), t))
                    bold = "Bold" in s["font"]
                    m = re.match(r"^([^\d:]{3,60}):", t)
                    if m:
                        labels[(creator, m.group(1).strip())] += 1
                    elif bold and not re.search(r"\d", t) and len(t) < 60:
                        labels[(creator, t)] += 1

for (creator, lab), n in sorted(labels.items()):
    print(f"{creator!s:22} {n:4} {lab}")
print("\n--- gyanús span (apró/oldalon kívüli):")
for o in odd:
    print(o)
