"""FastAPI backend.  Run:  uvicorn server:app --reload
Docs (auto-generated): http://127.0.0.1:8000/docs"""
import json
import re
import time
import uuid
from datetime import date, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import pymupdf
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

import db
from helpers import build_csv, recompute
from pipeline import process
from pipeline.qa import ask_all, ask_document
from pipeline.schemas import DOC_TYPES
from pipeline.validate import parse_number

UPLOADS = db.DATA_DIR / "uploads"
TEXT_DIR = db.DATA_DIR / "text"  # per-document page text and word boxes, used for questions
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg"}
MAX_MB = 20
PAGE_DPI = 110
pool = ThreadPoolExecutor(max_workers=2)  # the job queue: 2 documents at a time, the rest wait


@asynccontextmanager
async def lifespan(app: FastAPI):
    UPLOADS.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    db.init()
    yield


app = FastAPI(title="DocPipe", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],  # React dev server
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------- background worker ----------
def run_job(job_id: str) -> None:
    row = db.query("SELECT * FROM jobs WHERE id=?", (job_id,))[0]
    db.execute("UPDATE jobs SET status='processing', stage='reading', progress=1 WHERE id=?", (job_id,))

    def on_progress(stage, pct):
        db.execute("UPDATE jobs SET stage=?, progress=? WHERE id=?", (stage, pct, job_id))

    try:
        res = process(row["path"], doc_type=row["doc_type_hint"] or None, on_progress=on_progress)
        res.pop("file", None)  # do not expose server paths
        pages_data = res.pop("pages_data", None)
        if pages_data:
            (TEXT_DIR / f"{job_id}.json").write_text(json.dumps(pages_data), encoding="utf-8")
        db.execute(
            "UPDATE jobs SET status='done', stage='done', progress=100, result=?, finished_at=? WHERE id=?",
            (json.dumps(res, default=str), time.time(), job_id),
        )
    except Exception as e:
        db.execute(
            "UPDATE jobs SET status='failed', error=?, finished_at=? WHERE id=?",
            (str(e)[:500], time.time(), job_id),
        )


# ---------- helpers ----------
def _get_job(job_id: str) -> dict:
    rows = db.query("SELECT * FROM jobs WHERE id=?", (job_id,))
    if not rows:
        raise HTTPException(404, "Job not found")
    return rows[0]


def _public(row: dict, with_result: bool = False) -> dict:
    out = {k: row[k] for k in ("id", "filename", "status", "stage", "progress", "error", "created_at", "finished_at")}
    if row["result"]:
        res = json.loads(row["result"])
        out.update(doc_type=res["doc_type"], score=res["score"], needs_review=res["needs_review"])
        if with_result:
            out["result"] = res
    return out


# ---------- endpoints ----------
@app.get("/api/doc-types")
def doc_types():
    return {n: {"description": s["description"], "fields": list(s["fields"])} for n, s in DOC_TYPES.items()}


@app.post("/api/upload")
async def upload(files: list[UploadFile] = File(...), doc_type: str = Form("")):
    """Accepts one or many files. Returns job ids immediately; processing happens in the background."""
    if doc_type and doc_type not in DOC_TYPES:
        raise HTTPException(400, f"Unknown doc_type. Use one of: {', '.join(DOC_TYPES)}")
    for f in files:
        if Path(f.filename or "").suffix.lower() not in ALLOWED:
            raise HTTPException(400, f"Unsupported file type: {f.filename}. Use PDF, PNG or JPG.")
    jobs = []
    for f in files:
        data = await f.read()
        if len(data) > MAX_MB * 1024 * 1024:
            raise HTTPException(413, f"{f.filename} is larger than {MAX_MB} MB")
        job_id = uuid.uuid4().hex[:12]
        path = UPLOADS / f"{job_id}{Path(f.filename).suffix.lower()}"
        path.write_bytes(data)
        db.execute(
            "INSERT INTO jobs(id, filename, path, doc_type_hint, status, stage, progress, created_at) "
            "VALUES (?,?,?,?, 'queued', 'queued', 0, ?)",
            (job_id, Path(f.filename).name, str(path), doc_type, time.time()),
        )
        pool.submit(run_job, job_id)
        jobs.append({"id": job_id, "filename": f.filename})
    return {"jobs": jobs}


@app.get("/api/jobs")
def list_jobs():
    return [_public(r) for r in db.query("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 200")]


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    """Poll this every second or so to drive the progress bar."""
    return _public(_get_job(job_id), with_result=True)


@app.delete("/api/jobs/{job_id}")
def delete_job(job_id: str):
    """Remove a document completely: the file, its saved text, its answers, corrections and result."""
    row = _get_job(job_id)
    if row["status"] in ("queued", "processing"):
        raise HTTPException(409, "This document is still being processed. Try again when it has finished.")
    allowed = {UPLOADS.resolve(), TEXT_DIR.resolve()}
    for f in (Path(row["path"]), TEXT_DIR / f"{job_id}.json"):
        try:
            if f.resolve().parent in allowed:  # never delete anything outside our own folders
                f.unlink(missing_ok=True)
        except OSError:
            pass
    for table in ("qa", "corrections"):
        db.execute(f"DELETE FROM {table} WHERE job_id=?", (job_id,))
    db.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    return {"deleted": job_id}


@app.get("/api/jobs/{job_id}/pages/{n}")
def page_image(job_id: str, n: int):
    """PNG of page n, for the review screen. Highlight boxes are in PDF points:
    multiply by (displayed image width / page width from the result) to place them."""
    row = _get_job(job_id)
    doc = pymupdf.open(row["path"])
    try:
        if not 1 <= n <= len(doc):
            raise HTTPException(404, "Page not found")
        png = doc[n - 1].get_pixmap(dpi=PAGE_DPI).tobytes("png")
    finally:
        doc.close()
    return Response(png, media_type="image/png")


class Correction(BaseModel):
    value: str | None = None


@app.patch("/api/jobs/{job_id}/fields/{name}")
def correct_field(job_id: str, name: str, body: Correction):
    """Save a user's correction (or confirmation: send the same value). Kept as a training example."""
    row = _get_job(job_id)
    if row["status"] != "done":
        raise HTTPException(409, "Job is not finished")
    res = json.loads(row["result"])
    field = next((f for f in res["fields"] if f["name"] == name), None)
    if field is None:
        raise HTTPException(404, "Field not found")
    old = field["value"]
    new = (body.value or "").strip() or None
    field.update(value=new, status="corrected" if new else "missing", reasons=[], normalized=None)
    recompute(res)
    db.execute(
        "INSERT INTO corrections(job_id, doc_type, field, old_value, new_value, created_at) VALUES (?,?,?,?,?,?)",
        (job_id, res["doc_type"], name, None if old is None else str(old), new, time.time()),
    )
    db.execute("UPDATE jobs SET result=? WHERE id=?", (json.dumps(res, default=str), job_id))
    return _public({**row, "result": json.dumps(res, default=str)}, with_result=True)


@app.get("/api/corrections")
def corrections():
    """Every correction so far: the raw material for self-learning and fine-tuning."""
    return db.query("SELECT * FROM corrections ORDER BY id")


@app.get("/api/export.csv")
def export_csv(ids: str = ""):
    """One CSV for all finished documents (or only ?ids=a,b,c). Opens in Excel."""
    rows = db.query("SELECT filename, id, result FROM jobs WHERE status='done' ORDER BY created_at")
    if ids:
        wanted = set(ids.split(","))
        rows = [r for r in rows if r["id"] in wanted]
    return Response(
        build_csv(rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=export.csv"},
    )


# ---------- questions ----------
def _load_pages(job_id: str):
    f = TEXT_DIR / f"{job_id}.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else None


class Question(BaseModel):
    question: str = Field(min_length=2, max_length=500)


def _llm_error(e: Exception) -> HTTPException:
    return HTTPException(502, f"The language model could not answer right now. Try again in a moment. ({str(e)[:160]})")


@app.post("/api/jobs/{job_id}/ask")
def ask_one(job_id: str, body: Question):
    """Ask a question about one document. The answer comes with a checked source quote and its position."""
    row = _get_job(job_id)
    if row["status"] != "done":
        raise HTTPException(409, "This document is not finished yet.")
    pages = _load_pages(job_id)
    if not pages:
        raise HTTPException(409, "This document was processed before questions were available. Upload it again to ask questions.")
    try:
        out = ask_document(pages, body.question.strip())
    except Exception as e:
        raise _llm_error(e)
    db.execute("INSERT INTO qa(job_id, question, answer_json, created_at) VALUES (?,?,?,?)",
               (job_id, out["question"], json.dumps(out), time.time()))
    return out


@app.get("/api/jobs/{job_id}/qa")
def qa_history(job_id: str):
    _get_job(job_id)
    rows = db.query("SELECT answer_json FROM qa WHERE job_id=? ORDER BY id", (job_id,))
    return [json.loads(r["answer_json"]) for r in rows]


@app.post("/api/ask")
def ask_everything(body: Question):
    """Ask across all finished documents, e.g. 'which invoice has the highest total?'."""
    rows = db.query("SELECT id, filename, result FROM jobs WHERE status='done' ORDER BY created_at DESC LIMIT 60")
    docs = []
    for r in rows:
        res = json.loads(r["result"])
        docs.append({
            "id": r["id"], "filename": r["filename"], "doc_type": res["doc_type"], "score": res["score"],
            "needs_review": res["needs_review"], "fields": [(f["name"], f["value"]) for f in res["fields"]],
            "pages": _load_pages(r["id"]) or [],
        })
    if not docs:
        raise HTTPException(409, "Upload and process a document first.")
    try:
        return ask_all(docs, body.question.strip())
    except Exception as e:
        raise _llm_error(e)


# ---------- dashboard ----------
@app.get("/api/stats")
def stats():
    rows = db.query("SELECT id, filename, status, created_at, result FROM jobs ORDER BY created_at DESC")
    done = [(r, json.loads(r["result"])) for r in rows if r["status"] == "done" and r["result"]]
    field_counts = {k: 0 for k in ("verified", "corrected", "unverified", "invalid", "missing")}
    by_type, totals, review = {}, [], []
    for r, res in done:
        by_type[res["doc_type"]] = by_type.get(res["doc_type"], 0) + 1
        for k, v in res["counts"].items():
            field_counts[k] = field_counts.get(k, 0) + v
        if res["needs_review"]:
            review.append({"id": r["id"], "filename": r["filename"], "doc_type": res["doc_type"], "score": res["score"]})
        tot = next((f for f in res["fields"] if f["name"] == "total" and f["value"] is not None), None)
        cur = next((f["value"] for f in res["fields"] if f["name"] == "currency" and f["value"]), "")
        amount = parse_number(tot["value"]) if tot else None
        if amount is not None:
            totals.append({"id": r["id"], "filename": r["filename"], "amount": amount, "currency": cur})
    totals.sort(key=lambda t: -t["amount"])

    today = date.today()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    per_day = {d: 0 for d in days}
    for r in rows:
        d = datetime.fromtimestamp(r["created_at"]).date()
        if d in per_day:
            per_day[d] += 1

    scores = [res["score"] for _, res in done]
    secs = [res["seconds"] for _, res in done if res.get("seconds") is not None]
    return {
        "documents": len(rows),
        "processed": len(done),
        "in_queue": sum(r["status"] in ("queued", "processing") for r in rows),
        "failed": sum(r["status"] == "failed" for r in rows),
        "needs_review": len(review),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "avg_seconds": round(sum(secs) / len(secs), 1) if secs else None,
        "corrections": db.query("SELECT COUNT(*) AS n FROM corrections")[0]["n"],
        "questions": db.query("SELECT COUNT(*) AS n FROM qa")[0]["n"],
        "field_counts": field_counts,
        "by_type": by_type,
        "per_day": [{"day": d.strftime("%a"), "count": c} for d, c in per_day.items()],
        "top_totals": totals[:5],
        "review_list": review[:8],
    }


# ---------- serve the built React app (used in Docker / production) ----------
DIST = Path(__file__).parent / "frontend" / "dist"
if DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        f = (DIST / path).resolve()
        if path and f.is_file() and DIST.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(DIST / "index.html")
