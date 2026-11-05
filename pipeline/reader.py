"""Tier 1 + 2: read the text layer with PyMuPDF; fall back to OCR only for scans."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

import pymupdf as fitz  # PyMuPDF

MIN_TEXT_CHARS = 30   # fewer characters than this on a page => treat it as a scan
OCR_DPI = 200
MAX_PAGES = 50
_ocr_engine = None


@dataclass
class Word:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class Page:
    number: int
    width: float
    height: float
    text: str
    words: list[Word] = field(default_factory=list)
    source: str = "text_layer"  # or "ocr"


def _get_ocr():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def _ocr_page(page):
    pix = page.get_pixmap(dpi=OCR_DPI)
    result, _ = _get_ocr()(pix.tobytes("png"))
    scale = 72.0 / OCR_DPI  # pixels -> PDF points
    lines, words = [], []
    for box, text, _score in (result or []):
        xs = [p[0] for p in box]
        ys = [p[1] for p in box]
        x0, y0, x1, y1 = min(xs) * scale, min(ys) * scale, max(xs) * scale, max(ys) * scale
        lines.append(text)
        for tok in text.split():
            words.append(Word(tok, x0, y0, x1, y1))
    return "\n".join(lines), words


def read_document(path: str, on_page=None) -> list[Page]:
    """Works for PDFs and images (png/jpg). Returns one Page per page."""
    doc = fitz.open(path)
    pages: list[Page] = []
    total = min(len(doc), MAX_PAGES)
    for i in range(total):
        page = doc[i]
        text = page.get_text("text")
        if len(text.strip()) >= MIN_TEXT_CHARS:
            words = [Word(w[4], w[0], w[1], w[2], w[3]) for w in page.get_text("words")]
            source = "text_layer"
        else:
            text, words = _ocr_page(page)
            source = "ocr"
        pages.append(Page(i + 1, page.rect.width, page.rect.height, text, words, source))
        if on_page:
            on_page(i + 1, total, source)
    doc.close()
    return pages


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def locate(value, pages: list[Page]):
    """Find where a value appears. Returns (page_number, [x0, y0, x1, y1]) or None.
    Used later for click-to-highlight on the review screen."""
    target = _norm(str(value))
    if not target:
        return None
    for p in pages:
        toks = [(_norm(w.text), w) for w in p.words]
        toks = [t for t in toks if t[0]]
        for i in range(len(toks)):
            acc = ""
            for k in range(i, len(toks)):
                acc += toks[k][0]
                if acc == target:
                    ws = [t[1] for t in toks[i:k + 1]]
                    return p.number, [
                        min(w.x0 for w in ws), min(w.y0 for w in ws),
                        max(w.x1 for w in ws), max(w.y1 for w in ws),
                    ]
                if not target.startswith(acc):
                    break
    return None
