FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs

EXPOSE 8000

# Railway uses PORT env variable, fallback to 8000 for local dev
CMD uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}
