"""Szintetikus számla-PDF-ek a mintában nem szereplő elrendezésekhez."""
from __future__ import annotations

import html

import fitz

Item = tuple[float, float, str] | tuple[float, float, str, bool]


def make_pdf(pages: list[list[Item]]) -> bytes:
    doc = fitz.open()
    for items in pages:
        page = doc.new_page(width=595, height=842)
        for it in items:
            x, y, text = it[0], it[1], it[2]
            body = html.escape(text)
            if len(it) > 3 and it[3]:
                body = f"<b>{body}</b>"
            # Az insert_htmlbox Unicode-betűt használ (ő, ű, €), a Base14 nem.
            page.insert_htmlbox(fitz.Rect(x, y - 9, 590, y + 4), body, css="* {font-size: 9px; font-family: sans-serif;}")
    data = doc.tobytes()
    doc.close()
    return data
