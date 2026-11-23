"""Alkalmazás-beállítások kötelező környezeti változókból."""
from __future__ import annotations

import os
from pathlib import Path


def _require(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"Hiányzó környezeti változó: {name}")
    return value


OUR_COMPANY_NAME = _require("OUR_COMPANY_NAME")
OUR_TAX_IDS = [t.strip() for t in _require("OUR_TAX_IDS").split(",") if t.strip()]

DATA_DIR = Path(_require("DATA_DIR"))
DB_PATH = DATA_DIR / "invoices.sqlite"

MNB_ENDPOINT = _require("MNB_ENDPOINT")
