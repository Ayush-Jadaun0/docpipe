"""Question answering over one document or many, with source checking.

Every answer must cite a short quote. We then check the quote really appears in the
document (and find its position for highlighting), and flag numbers in the answer
that do not appear anywhere in the text."""
from __future__ import annotations

import re

from . import privacy
from .extract import _call, _parse_json
from .reader import Page, Word, locate
from .validate import _norm, _numbers_in

QA_SYSTEM = (
    "You answer questions about documents using ONLY the text you are given. "
    "Never use outside knowledge and never guess. If the text does not contain the answer, say so. "
    "Return ONLY a JSON object, no prose and no markdown."
)
STOP = set("a an the is are was were of to in on for and or by with what which who whom when where how "
           "does do did this that it its from as at be has have had".split())


def _tokens(s: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", s.lower()) if t not in STOP and len(t) > 1}


def _chunks(pages: list[dict], size: int = 700) -> list[tuple[int, str]]:
    out = []
    for p in pages:
        cur = ""
        for line in p["text"].splitlines():
            if cur and len(cur) + len(line) > size:
                out.append((p["number"], cur))
                cur = ""
            cur += line + "\n"
        if cur.strip():
            out.append((p["number"], cur))
    return out


def build_context(pages: list[dict], question: str, budget: int = 12000) -> str:
    """Whole document if it is short; otherwise the passages that best match the question."""
    if sum(len(p["text"]) for p in pages) <= budget:
        return "\n\n".join(f"[page {p['number']}]\n{p['text']}" for p in pages)
    q = _tokens(question)
    scored = [(len(q & _tokens(c)), -i, i, n, c[:2100]) for i, (n, c) in enumerate(_chunks(pages))]
    scored.sort(reverse=True)
    picked, used = [], 0
    for _score, _neg, i, n, c in scored:
        if used + len(c) > budget:
            continue
        picked.append((n, i, c))
        used += len(c)
    picked.sort()
    return "\n\n".join(f"[page {n}]\n{c}" for n, _i, c in picked)


def _page_objs(pages: list[dict]) -> list[Page]:
    return [Page(p["number"], p["width"], p["height"], p["text"], [Word(*w) for w in p["words"]], "stored")
            for p in pages]


def _unknown_numbers(answer: str, source_text: str) -> list[float]:
    have = _numbers_in(source_text)
    out = []
    for n in _numbers_in(answer):
        if n < 100 and float(n).is_integer():
            continue  # small whole numbers are usually counts or page numbers
        if not any(abs(n - h) < 0.005 for h in have):
            out.append(n)
    return out


def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def ask_document(pages: list[dict], question: str) -> dict:
    context = build_context(pages, question)
    masked, mapping = privacy.mask(context)
    prompt = (
        f"Question: {question}\n\nDOCUMENT TEXT (pages are marked like [page 2]):\n{masked}\n\n"
        'Return JSON: {"found": true or false, "answer": "short, direct answer", '
        '"page": page number the answer comes from or null, '
        '"quote": "one short phrase copied EXACTLY from the document that supports the answer (under 20 words) or null"}\n'
        'If the document does not contain the answer, use found=false and answer "The document does not say."'
    )
    data = _parse_json(_call(prompt, 1500, system=QA_SYSTEM))
    found = bool(data.get("found"))
    answer = privacy.unmask(str(data.get("answer") or ""), mapping)
    quote = privacy.unmask(data.get("quote"), mapping) if found else None
    out = {"question": question, "answer": answer, "found": found, "quote": quote,
           "page": None, "bbox": None, "verified": False, "warnings": []}
    if not found:
        return out

    objs = _page_objs(pages)
    hint = _as_int(data.get("page"))
    src = None
    if quote:
        for p in sorted(objs, key=lambda p: p.number != hint):  # the page the model named first
            hit = locate(quote, [p])
            if hit:
                src = {"page": hit[0], "bbox": hit[1]}
                break
        if src is None:
            qn = _norm(quote)
            page_no = next((p["number"] for p in pages if qn and qn in _norm(p["text"])), None)
            if page_no:
                src = {"page": page_no, "bbox": None}
    if src:
        out.update(page=src["page"], bbox=src["bbox"], verified=True)
    else:
        out["page"] = hint
        out["warnings"].append("The quoted source was not found in the document. Treat this answer with caution.")

    full_text = "\n".join(p["text"] for p in pages)
    unknown = _unknown_numbers(answer, full_text)
    if unknown:
        out["warnings"].append(
            "These figures are not written in the document (they may be calculated): "
            + ", ".join(f"{n:g}" for n in unknown))
    return out


def ask_all(docs: list[dict], question: str) -> dict:
    """docs: newest first; each has id, filename, doc_type, score, needs_review, fields [(name, value)], pages."""
    lines, used, truncated = [], 0, False
    for d in docs:
        vals = "; ".join(f"{n}={v}" for n, v in d["fields"] if v not in (None, ""))
        line = (f'[{d["id"]}] {d["filename"]} | {d["doc_type"]} | score {d["score"]} | '
                f'{"needs review" if d["needs_review"] else "checked"} | {vals}')
        if used + len(line) > 6000:
            truncated = True
            break
        lines.append(line)
        used += len(line) + 1
    searched = len(lines)

    q = _tokens(question)
    cand = []
    for d in docs[:searched]:
        for n, c in _chunks(d["pages"]):
            sc = len(q & _tokens(c))
            if sc:
                cand.append((sc, d["id"], n, c[:1500]))
    cand.sort(key=lambda x: -x[0])
    excerpts, used = [], 0
    for _sc, did, n, c in cand[:12]:
        if used + len(c) > 5000:
            continue
        excerpts.append(f"[{did} page {n}]\n{c}")
        used += len(c)

    context = "STRUCTURED DATA (one line per document)\n" + "\n".join(lines) + "\n\nEXCERPTS\n" + "\n\n".join(excerpts)
    masked, mapping = privacy.mask(context)
    prompt = (
        f"Question: {question}\n\n{masked}\n\n"
        "Use the structured data for comparisons, totals and counts, and compare numbers carefully. "
        "Name documents by file name in the answer.\n"
        'Return JSON: {"answer": "short, direct answer", "sources": [{"doc": "id from the square brackets", "page": number or null}]}\n'
        "Only cite ids that appear above. If the documents do not contain the answer, say so."
    )
    data = _parse_json(_call(prompt, 1500, system=QA_SYSTEM))
    answer = privacy.unmask(str(data.get("answer") or ""), mapping)
    names = {d["id"]: d["filename"] for d in docs}
    sources, seen = [], set()
    for s in data.get("sources") or []:
        did = str(s.get("doc", "")) if isinstance(s, dict) else ""
        if did in names and did not in seen:
            seen.add(did)
            sources.append({"doc": did, "filename": names[did], "page": _as_int(s.get("page"))})
    warnings = []
    unknown = _unknown_numbers(answer, context)
    if unknown:
        warnings.append("These figures are not written in the documents (they may be calculated): "
                        + ", ".join(f"{n:g}" for n in unknown))
    return {"question": question, "answer": answer, "sources": sources, "searched": searched,
            "total": len(docs), "truncated": truncated, "warnings": warnings}
