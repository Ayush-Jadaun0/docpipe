"""Validation layer: format checks, arithmetic checks, and 'value appears in the text'."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from dateutil import parser as dtparser

from .schemas import DOC_TYPES

VERIFIED, UNVERIFIED, INVALID, MISSING = "verified", "unverified", "invalid", "missing"
WEIGHT = {VERIFIED: 1.0, UNVERIFIED: 0.5, INVALID: 0.0}

FORMAT_PATTERNS = {
    "pan_number": re.compile(r"^[A-Z]{5}\d{4}[A-Z]$"),
    "aadhaar_number": re.compile(r"^\d{4}\s?\d{4}\s?\d{4}$"),
    "gstin": re.compile(r"^\d{2}[A-Z]{5}\d{4}[A-Z]\dZ[A-Z\d]$"),
}


@dataclass
class FieldResult:
    name: str
    value: object = None
    normalized: object = None
    status: str = MISSING
    reasons: list = field(default_factory=list)
    page: int | None = None
    bbox: list | None = None


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(s).lower())


def parse_number(v):
    s = re.sub(r"[^\d.,\-]", "", str(v)).replace(",", "")
    if not re.search(r"\d", s):
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _numbers_in(text: str) -> list[float]:
    out = []
    for m in re.finditer(r"\d[\d,]*(?:\.\d+)?", text):
        try:
            out.append(float(m.group(0).replace(",", "")))
        except ValueError:
            pass
    return out


def _check(name, ftype, value, text_norm, text_numbers) -> FieldResult:
    r = FieldResult(name=name, value=value)
    if value is None or str(value).strip() == "":
        r.value = None
        return r
    sval = str(value).strip()
    invalid, in_text = False, False

    pat = FORMAT_PATTERNS.get(name)
    if pat and not pat.match(sval.upper() if name != "aadhaar_number" else sval):
        invalid = True
        r.reasons.append("wrong format")

    if ftype == "number":
        num = parse_number(sval)
        if num is None:
            invalid = True
            r.reasons.append("not a valid number")
        else:
            r.normalized = num
            in_text = any(abs(num - n) < 0.005 for n in text_numbers)
    elif ftype == "date":
        try:
            r.normalized = dtparser.parse(sval, dayfirst=True).date().isoformat()
        except (ValueError, OverflowError):
            invalid = True
            r.reasons.append("not a valid date")
        in_text = _norm(sval) in text_norm
    else:
        in_text = _norm(sval) in text_norm

    if invalid:
        r.status = INVALID
    elif in_text:
        r.status = VERIFIED
    else:
        r.status = UNVERIFIED
        r.reasons.append("value not found in document text")
    return r


def _cross_check(results: list[FieldResult]) -> None:
    by = {r.name: r for r in results}
    parts = [by.get(k) for k in ("subtotal", "tax", "total")]
    if all(p and isinstance(p.normalized, float) for p in parts):
        sub, tax, tot = (p.normalized for p in parts)
        disc_r = by.get("discount")
        disc = abs(disc_r.normalized) if disc_r and isinstance(disc_r.normalized, float) else 0.0
        if abs(sub - disc + tax - tot) > max(0.05, 0.005 * abs(tot)):
            msg = f"subtotal - discount + tax != total ({sub} - {disc} + {tax} != {tot})"
            for p in parts + ([disc_r] if disc else []):
                p.status = INVALID
                p.reasons.append(msg)


def validate(fields: dict, doc_type: str, text: str) -> list[FieldResult]:
    text_norm, text_numbers = _norm(text), _numbers_in(text)
    spec = DOC_TYPES[doc_type]["fields"]
    results = [
        _check(name, spec[name][0], fields.get(name), text_norm, text_numbers)
        for name in spec
    ]
    _cross_check(results)
    return results


def score(results: list[FieldResult]) -> float:
    scored = [r for r in results if r.status != MISSING]
    if not scored:
        return 0.0
    return round(100 * sum(WEIGHT[r.status] for r in scored) / len(scored), 1)
