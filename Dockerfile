# ---- stage 1: build the React frontend ----
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ---- stage 2: Python backend + built frontend ----
FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 DATA_DIR=/app/data

# libs needed by onnxruntime / opencv (rapidocr)
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
COPY --from=frontend /app/frontend/dist ./frontend/dist

VOLUME /app/data
EXPOSE 8000
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
