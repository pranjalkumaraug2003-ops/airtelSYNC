# Udyam Digital API: FastAPI + Tesseract OCR, deployed on Render.
FROM python:3.13-slim

# Tesseract reads KYC documents on our own server (documents never go to an AI API).
RUN apt-get update \
 && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-eng libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY data ./data
COPY tests ./tests
COPY scripts ./scripts

# Run as a non-root user.
RUN useradd -m appuser && chown -R appuser /app
USER appuser

ENV PORT=8000
ENV OMP_THREAD_LIMIT=1
EXPOSE 8000
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
