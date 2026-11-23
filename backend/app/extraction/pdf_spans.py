"""PDF -> koordinátás szövegdarabok (span), az oldalak egymás alá fűzve."""
from __future__ import annotations

from dataclasses import dataclass

import fitz


class PdfReadError(Exception):
    """A fájl nem olvasható PDF, vagy nincs benne szöveg."""


@dataclass(frozen=True)
class Span:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    page: int
    bold: bool
    size: float

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return self.y1 - self.y0


PAGE_GAP = 20.0


def load_spans(data: bytes) -> list[Span]:
    # A PyMuPDF a szöveges fájlt is megnyitná, ezért a PDF-fejléc kötelező.
    if b"%PDF-" not in data[:1024]:
        raise PdfReadError("Nem PDF-fájl")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PdfReadError(f"Sérült vagy nem olvasható PDF ({exc})") from exc
    spans: list[Span] = []
    offset = 0.0
    with doc:
        repaired = doc.is_repaired
        if doc.is_encrypted and not doc.authenticate(""):
            raise PdfReadError("Jelszóval védett PDF")
        for pno, page in enumerate(doc):
            rect = page.rect
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for s in line["spans"]:
                        text = " ".join(s["text"].split())
                        x0, y0, x1, y1 = s["bbox"]
                        # Láthatatlan vagy lapon kívüli szöveg kimarad.
                        if not text or s["size"] < 3 or x1 < 0 or y1 < 0 or x0 > rect.width or y0 > rect.height:
                            continue
                        spans.append(Span(text, x0, y0 + offset, x1, y1 + offset, pno, "bold" in s["font"].lower(), s["size"]))
            offset += rect.height + PAGE_GAP
    if not spans:
        # Csonka fájlnál a MuPDF javítást jelez, ez nem szkennelt kép.
        raise PdfReadError("Sérült vagy csonka PDF, nem olvasható tartalom" if repaired else "A PDF-ben nincs kinyerhető szöveg (szkennelt kép?)")
    return spans


def full_text(spans: list[Span]) -> str:
    """Olvasási sorrendű szöveg: soronként, balról jobbra."""
    lines: list[list[Span]] = []
    for sp in sorted(spans, key=lambda s: (s.cy, s.x0)):
        if lines and abs(lines[-1][0].cy - sp.cy) < max(2.0, sp.height * 0.4):
            lines[-1].append(sp)
        else:
            lines.append([sp])
    return "\n".join(" ".join(s.text for s in sorted(ln, key=lambda s: s.x0)) for ln in lines)
