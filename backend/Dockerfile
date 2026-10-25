# Build context must be the REPO ROOT (not the backend/ folder).
# Render: dockerfilePath: Dockerfile  dockerContext: .
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install deps first (layer-cached until requirements.txt changes)
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy application code and bundled data from the repo root
COPY backend /app/backend
COPY data    /app/data
COPY evidence /app/evidence

WORKDIR /app/backend

ENV PYTHONPATH=/app/backend:/app
ENV PORT=8000
ENV DATABASE_URL=sqlite:////app/data/miragenet.db
ENV CORS_ORIGINS=*

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://127.0.0.1:${PORT}/api/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
