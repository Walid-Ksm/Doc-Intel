# ==============================================================================
# Document Intelligence Service (FastAPI P1 & Celery Worker)
# Production Container Image
# ==============================================================================

FROM python:3.11-slim as runtime

# Prevent Python from writing .pyc files and enable unbuffered output
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

WORKDIR /app

# Install system runtime dependencies (libpq for postgres, curl for healthchecks, poppler/tesseract for doc processing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged system user for process isolation
RUN groupadd -g 10001 appuser && \
    useradd -u 10001 -g appuser -s /bin/bash -m appuser

# Install Python build tools and dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source code and infrastructure scripts
COPY app/ ./app/
COPY infra/ ./infra/

# Ensure ownership of working directory and site-packages (for rapidocr/huggingface model downloads)
ENV HF_HOME=/app/.cache/huggingface \
    TORCH_HOME=/app/.cache/torch

RUN mkdir -p /home/appuser/.cache /app/.cache /usr/local/lib/python3.11/site-packages/rapidocr/models && \
    chown -R appuser:appuser /home/appuser /app /usr/local/lib/python3.11/site-packages/rapidocr

USER appuser

EXPOSE 8000

# Health check verifies the FastAPI readiness endpoint
HEALTHCHECK --interval=15s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Default command launches the FastAPI Uvicorn ASGI server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
