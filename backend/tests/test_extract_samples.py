"""Regresszió a 100 mintán; az elvárt értékek kézi és független kontrollal ellenőrzött kimenetből."""
import json
from pathlib import Path

import pytest

from app.extraction.extractor import extract
from tests.samples import SAMPLES_DIR

ROOT = Path(__file__).resolve().parent.parent
EXPECTED = json.loads((ROOT / "tests" / "fixtures" / "expected_samples.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_sample_invoice(name):
    ex = extract((SAMPLES_DIR / name).read_bytes())
    exp = EXPECTED[name]
    got = {
        "no": ex.invoice_no, "dir": ex.direction, "issue": str(ex.issue_date), "supply": str(ex.supply_date),
        "due": str(ex.due_date), "cur": ex.currency, "gross": str(ex.gross_total), "partner_ids": ex.partner.tax_ids,
    }
    assert got == exp
    assert not ex.errors
    assert ex.net_total + ex.vat_total == ex.gross_total
