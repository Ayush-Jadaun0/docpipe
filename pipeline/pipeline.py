"""Orchestrates: read -> classify -> extract -> validate (+1 retry) -> locate."""
from __future__ import annotations

import time
from dataclasses import asdict

from . import privacy
from .extract import classify, extract_fields
from .reader import locate, read_document
from .validate import INVALID, MISSING, UNVERIFIED, VERIFIED, score, validate

AUTO_APPROVE_SCORE = 90.0


def process(path: str, doc_type: str | None = None, on_progress=None,
            mask_pii: bool = True, retry: bool = True) -> dict:
    """on_progress(stage: str, percent: int) is called as work proceeds,
    so the frontend can show a real progress bar."""
    def report(stage, pct):
        if on_progress:
            on_progress(stage, pct)

    t0 = time.perf_counter()
    timings: dict[str, float] = {}

    # 1. read
    report("reading", 5)
    pages = read_document(
        path,
        on_page=lambda i, n, src: report("ocr" if src == "ocr" else "reading", 5 + int(30 * i / n)),
    )
    full_text = "\n\n".join(f"--- page {p.number} ---\n{p.text}" for p in pages)
    if not full_text.replace("-", "").strip():
        raise ValueError("No text could be read from this document.")
    timings["read"] = round(time.perf_counter() - t0, 2)

    llm_text, mapping = privacy.mask(full_text) if mask_pii else (full_text, {})

    # 2. classify
    t = time.perf_counter()
    report("classifying", 40)
    doc_type = doc_type or classify(llm_text)
    timings["classify"] = round(time.perf_counter() - t, 2)

    # 3. extract
    t = time.perf_counter()
    report("extracting", 55)
    raw = extract_fields(doc_type, llm_text)
    fields = {k: privacy.unmask(v, mapping) for k, v in raw.items()}
    timings["extract"] = round(time.perf_counter() - t, 2)

    # 4. validate, then one focused retry for failed fields
    report("validating", 75)
    results = validate(fields, doc_type, full_text)
    if retry:
        bad = {r.name: "; ".join(r.reasons) for r in results if r.status in (INVALID, UNVERIFIED)}
        if bad:
            report("retrying", 80)
            try:
                again = extract_fields(doc_type, llm_text, only=list(bad), feedback=bad)
                merged = dict(fields)
                merged.update({k: privacy.unmask(v, mapping) for k, v in again.items()})
                new_results = validate(merged, doc_type, full_text)
                if score(new_results) >= score(results):  # keep only if not worse
                    results = new_results
            except Exception:
                pass  # keep first-pass results

    # 5. locate each value on the page (for click-to-highlight)
    report("locating", 90)
    for r in results:
        if r.value is not None:
            hit = locate(r.value, pages)
            if hit:
                r.page, r.bbox = hit

    total_score = score(results)
    counts = {s: sum(r.status == s for r in results) for s in (VERIFIED, UNVERIFIED, INVALID, MISSING)}
    report("done", 100)
    return {
        "file": path,
        "doc_type": doc_type,
        "pages": [
            {"number": p.number, "source": p.source, "chars": len(p.text),
             "width": p.width, "height": p.height}
            for p in pages
        ],
        "fields": [asdict(r) for r in results],
        "pages_data": [
            {"number": p.number, "width": p.width, "height": p.height, "text": p.text,
             "words": [[w.text, round(w.x0, 1), round(w.y0, 1), round(w.x1, 1), round(w.y1, 1)] for w in p.words]}
            for p in pages
        ],
        "score": total_score,
        "counts": counts,
        "needs_review": total_score < AUTO_APPROVE_SCORE or counts[INVALID] > 0,
        "seconds": round(time.perf_counter() - t0, 2),
        "timings": timings,
    }
