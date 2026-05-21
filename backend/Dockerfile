# Starter backend image — extend as app grows (doc 6, doc 12)
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data/uploads

EXPOSE 8000

# Default CMD overridden by docker-compose for --reload in local dev
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
