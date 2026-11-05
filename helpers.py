"""Pure helper functions (no web framework) so they are easy to test."""
import csv
import io
import json

WEIGHT = {"verified": 1.0, "corrected": 1.0, "unverified": 0.5, "invalid": 0.0}
AUTO_APPROVE_SCORE = 90.0


def recompute(result: dict) -> dict:
    """Recalculate score/counts/needs_review after a user correction."""
    fields = result["fields"]
    counts = {s: 0 for s in ("verified", "corrected", "unverified", "invalid", "missing")}
    for f in fields:
        counts[f["status"]] = counts.get(f["status"], 0) + 1
    scored = [f for f in fields if f["status"] != "missing"]
    result["score"] = (
        round(100 * sum(WEIGHT[f["status"]] for f in scored) / len(scored), 1) if scored else 0.0
    )
    result["counts"] = counts
    result["needs_review"] = result["score"] < AUTO_APPROVE_SCORE or counts["invalid"] > 0
    return result


def safe_cell(value):
    """Stop spreadsheet formula injection: text from uploaded documents is untrusted."""
    if value is None:
        return ""
    s = str(value)
    if s[:1] in ("=", "+", "-", "@"):
        try:
            float(s.replace(",", "").replace("$", ""))
        except ValueError:
            return "'" + s
    return s


def build_csv(rows: list[dict]) -> str:
    """rows: DB rows with 'filename' and 'result' (JSON string). One line per document."""
    docs, names = [], []
    for r in rows:
        res = json.loads(r["result"])
        docs.append((r["filename"], res))
        for f in res["fields"]:
            if f["name"] not in names:
                names.append(f["name"])
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["file", "doc_type", "score", "needs_review"] + names)
    for filename, res in docs:
        by = {f["name"]: f["value"] for f in res["fields"]}
        w.writerow(
            [safe_cell(filename), res["doc_type"], res["score"], res["needs_review"]]
            + [safe_cell(by.get(n)) for n in names]
        )
    return "\ufeff" + buf.getvalue()  # BOM so Excel reads UTF-8 correctly
