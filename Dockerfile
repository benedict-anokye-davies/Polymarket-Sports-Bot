FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Install safe-pysha3 first (Python 3.11 compatible fork of pysha3),
# then eip712-structs without deps (so it skips broken pysha3),
# then the rest of the requirements.
RUN pip install --no-cache-dir safe-pysha3==1.0.4 && \
    pip install --no-cache-dir --no-deps eip712-structs==1.1.0 && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs

EXPOSE 8000

# Railway uses PORT env variable, fallback to 8000 for local dev
CMD sh -c "uvicorn src.main:app --host 0.0.0.0 --port \${PORT:-8000}"
