"""Tier 3: LLM/VLM extraction into fixed JSON fields.

Swap this module to use another model (e.g. a LoRA-tuned Qwen-VL on Colab):
keep the two function signatures `classify()` and `extract_fields()` the same.
"""
from __future__ import annotations

import json
import os
import re

from .schemas import DOC_TYPES

PROVIDER = os.getenv("LLM_PROVIDER", "groq")  # "groq" (free), "gemini" (free) or "anthropic"
# Several models can be given, comma separated; if one is busy or missing, the next is tried.
MODELS = {
    "groq": os.getenv("GROQ_MODEL", "openai/gpt-oss-120b,openai/gpt-oss-20b"),
    "gemini": os.getenv("GEMINI_MODEL", "gemini-3-flash-preview"),
    "anthropic": os.getenv("EXTRACT_MODEL", "claude-sonnet-5-5"),
}
MAX_CHARS = 12000
TRANSIENT = ("503", "504", "429", "500", "413", "404", "UNAVAILABLE", "DEADLINE",
             "NOT_FOUND", "timed out", "Timeout", "rate_limit")
_client = None

SYSTEM = (
    "You are a precise document-extraction engine. Return ONLY a JSON object, no prose, "
    "no markdown. Copy every value exactly as it is written in the document (do not reformat, "
    "translate or correct it). If a field is not present, use null. Never guess or invent values."
)


def _groq(model: str, prompt: str, max_tokens: int, system: str = SYSTEM) -> str:
    import httpx
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY is not set")
    r = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={"Authorization": f"Bearer {key}"},
        json={
            "model": model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}],
            "temperature": 0,
            "max_tokens": max(max_tokens, 3000),  # reasoning models spend tokens thinking
            "response_format": {"type": "json_object"},
        },
        timeout=60,
    )
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"] or ""


def _gemini(model: str, prompt: str, max_tokens: int, system: str = SYSTEM) -> str:
    global _client
    from google import genai
    if _client is None:
        _client = genai.Client(http_options={"timeout": 60000})  # milliseconds
    resp = _client.models.generate_content(
        model=model,
        contents=prompt,
        config={
            "system_instruction": system,
            "response_mime_type": "application/json",
            "max_output_tokens": max_tokens,
        },
    )
    return resp.text or ""


def _anthropic(model: str, prompt: str, max_tokens: int, system: str = SYSTEM) -> str:
    global _client
    from anthropic import Anthropic
    if _client is None:
        _client = Anthropic()  # reads ANTHROPIC_API_KEY
    resp = _client.messages.create(
        model=model, max_tokens=max_tokens, system=system,
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(b.text for b in resp.content if b.type == "text")


def _call(prompt: str, max_tokens: int = 1500, system: str = SYSTEM) -> str:
    import time
    fn = {"groq": _groq, "gemini": _gemini, "anthropic": _anthropic}[PROVIDER]
    models = [m.strip() for m in MODELS[PROVIDER].split(",") if m.strip()]
    last_err = None
    for attempt in range(3):
        for model in models:
            try:
                return fn(model, prompt, max_tokens, system)
            except Exception as e:  # busy / rate limited / wrong model: try next, then wait
                last_err = e
                if not any(t in str(e) for t in TRANSIENT):
                    raise
        time.sleep(3 * (attempt + 1))
    raise last_err


def _parse_json(raw: str) -> dict:
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        raise ValueError("Model did not return JSON")
    return json.loads(raw[start:end + 1])


def _keyword_guess(text: str) -> str:
    low = text.lower()
    best, best_hits = "other", 0
    for name, spec in DOC_TYPES.items():
        hits = sum(k in low for k in spec["keywords"])
        if hits > best_hits:
            best, best_hits = name, hits
    return best


def classify(text: str) -> str:
    options = "\n".join(f"- {n}: {s['description']}" for n, s in DOC_TYPES.items())
    prompt = (
        f"Classify this document into exactly one type.\n{options}\n\n"
        f'Return JSON like {{"type": "invoice"}}.\n\nDOCUMENT:\n{text[:4000]}'
    )
    try:
        label = _parse_json(_call(prompt, 50)).get("type", "other")
        return label if label in DOC_TYPES else "other"
    except Exception:
        return _keyword_guess(text)


def extract_fields(doc_type: str, text: str, only=None, feedback=None) -> dict:
    fields = DOC_TYPES[doc_type]["fields"]
    names = [n for n in fields if only is None or n in only]
    spec = "\n".join(f'- "{n}" ({fields[n][0]}): {fields[n][1]}' for n in names)
    prompt = f"Extract these fields from the document as a JSON object:\n{spec}\n"
    if feedback:
        issues = "\n".join(f'- "{k}": {v}' for k, v in feedback.items())
        prompt += (
            "\nA previous attempt failed validation for these fields. "
            f"Re-read the document carefully:\n{issues}\n"
        )
    prompt += f"\nDOCUMENT:\n{text[:MAX_CHARS]}"
    data = _parse_json(_call(prompt))
    return {n: data.get(n) for n in names}
