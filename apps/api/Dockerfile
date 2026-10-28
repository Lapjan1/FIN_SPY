# Dockerfile for FIN_SPY API - Railway deployment for Paystack live URL proof
# Loopback 127.0.0.1 binding dev but 0.0.0.0 prod
FROM python:3.12-slim

WORKDIR /app

# Install system deps for PyMuPDF, cryptography, psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential libffi-dev libssl-dev curl && \
    rm -rf /var/lib/apt/lists/*

# Copy dependency files
COPY pyproject.toml ./
COPY README.md ./
# Copy only API and worker and packages needed
COPY apps/api ./apps/api
COPY apps/worker ./apps/worker
COPY packages ./packages
COPY config ./config
COPY docs ./docs

# Install Python deps
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir fastapi uvicorn pydantic python-multipart openai python-dotenv PyMuPDF pdfplumber openpyxl XlsxWriter reportlab pyHanko cryptography pillow python-dateutil passlib[bcrypt] bcrypt psycopg2-binary requests python-multipart

# Env
ENV PYTHONPATH=/app
ENV PORT=8000

# Healthcheck per Railway go-live checklist: Ensure webhook URL publicly available, return 200 OK
HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -f http://localhost:8000/health/ready || exit 1

# Expose
EXPOSE 8000

# Start - per railway.json healthcheckPath /health/ready
CMD ["sh", "-c", "uvicorn apps.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
