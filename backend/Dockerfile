# Standalone backend Dockerfile (supports build context: backend/ OR repo-root via root Dockerfile)
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt

# Copy backend application source and bundled data
COPY . /app/backend

# Ensure /app/data and /app/evidence exist in root /app for paths like /app/data/miragenet.db
RUN if [ -d "/app/backend/data" ]; then cp -r /app/backend/data /app/data; else mkdir -p /app/data; fi \
    && if [ -d "/app/backend/evidence" ]; then cp -r /app/backend/evidence /app/evidence; else mkdir -p /app/evidence; fi

WORKDIR /app/backend

ENV PYTHONPATH=/app/backend:/app
ENV PORT=8000
ENV DATABASE_URL=sqlite:////app/data/miragenet.db
ENV CORS_ORIGINS=*

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://127.0.0.1:${PORT}/api/health || exit 1

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
