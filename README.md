# DocPipe

Document understanding pipeline: upload invoices, receipts or ID cards (PDF/PNG/JPG) → OCR + LLM extraction → validation → review UI, Q&A over documents, CSV export.

**Stack:** FastAPI · React (Vite) · SQLite · PyMuPDF · RapidOCR · Groq / Gemini / Anthropic

## Run with Docker (recommended)

```bash
cp .env.example .env      # add ONE API key (Groq and Gemini have free tiers)
docker compose up --build
```
Open http://localhost:8000  (API docs: http://localhost:8000/docs)

Or without compose:
```bash
docker build -t docpipe .
docker run -p 8000:8000 --env-file .env -v docpipe-data:/app/data docpipe
```

## Run locally (development)

```bash
pip install -r requirements.txt
uvicorn server:app --reload            # backend  -> http://127.0.0.1:8000
cd frontend && npm install && npm run dev   # frontend -> http://localhost:5173
```

CLI: `python run.py sample/invoice.png --type invoice`

## Configuration

| Variable | Purpose |
|---|---|
| `LLM_PROVIDER` | `groq` (default), `gemini` or `anthropic` |
| `GROQ_API_KEY` / `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` | key for the chosen provider |
| `DATA_DIR` | where the database and uploads are stored (default `./data`) |
