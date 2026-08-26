# NER Road Accessibility API
# Build:  docker build -t ner-backend .
# Run:    docker run -p 8000:8000 --env-file .env ner-backend
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# geopandas/shapely/osmnx need GEOS + PROJ; psycopg[binary] needs libpq.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgeos-c1v5 \
        libproj25 \
        libpq5 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY load_ner.py check_contract.py ./

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
