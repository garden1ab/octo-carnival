# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-slim AS frontend-builder

WORKDIR /frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build


# ── Stage 2: Build Python deps ────────────────────────────────────────────────
FROM python:3.11-slim AS py-builder

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 3: Runtime ─────────────────────────────────────────────────────────
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libxml2 libxslt1.1 \
    && rm -rf /var/lib/apt/lists/*

COPY --from=py-builder /install /usr/local
COPY --from=frontend-builder /frontend/dist ./frontend/dist

COPY . .
RUN mkdir -p /app/uploads

EXPOSE 8000

ENV HOST=0.0.0.0
ENV PORT=8000
ENV LOG_LEVEL=INFO
ENV UPLOAD_DIR=/app/uploads

RUN useradd --create-home appuser && chown -R appuser:appuser /app
USER appuser

CMD ["python", "main.py"]
