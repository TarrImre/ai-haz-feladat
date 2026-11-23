"""A kinyerő futtatása a mintán; táblázat a konzolra, JSON a scripts/out-ba."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.extraction.extractor import extract  # noqa: E402

sys.stdout.reconfigure(encoding="utf-8")
rows = []
for pdf in sorted((ROOT.parent / "invoices").glob("*.pdf")):
    try:
        ex = extract(pdf.read_bytes())
    except Exception as exc:
        print(f"{pdf.name:32} EXC {exc!r}")
        continue
    p = ex.partner
    row = {
        "file": pdf.name, "no": ex.invoice_no, "dir": ex.direction, "seller": ex.seller.name, "seller_ids": ex.seller.tax_ids,
        "buyer": ex.buyer.name, "buyer_ids": ex.buyer.tax_ids, "issue": str(ex.issue_date), "supply": str(ex.supply_date),
        "due": str(ex.due_date), "cur": ex.currency, "gross": str(ex.gross_total), "net": str(ex.net_total),
        "vat": str(ex.vat_total), "warn": ex.warnings, "err": ex.errors,
    }
    rows.append(row)
    flag = "ERR" if ex.errors else ("WRN" if ex.warnings else "ok ")
    print(f"{pdf.name[:30]:30} {flag} {ex.invoice_no!s:15} {ex.direction!s:6} {str(p.name)[:26]:26} {','.join(p.tax_ids)[:24]:24} "
          f"{ex.issue_date} {ex.supply_date} {ex.due_date} {ex.currency} {ex.gross_total!s:>12} {'; '.join(ex.errors + ex.warnings)[:80]}")
(ROOT / "scripts" / "out" / "extract.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
