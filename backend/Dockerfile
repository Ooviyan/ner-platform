# NER Road Accessibility API
# Build:  docker build -t ner-backend .
# Run:    docker run -p 8000:8000 --env-file .env ner-backend
# 3.12+: xgboost 3.3 and later require it, and the risk model must be
# scored by the SAME xgboost that trained it - see ml/risk.py _load().
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# geopandas/shapely/osmnx need GEOS + PROJ; psycopg[binary] needs libpq.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgeos-c1v5 \
        libproj25 \
        libpq5 \
        libgomp1 \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY load_ner.py check_contract.py ./

# Person 2's models are NOT baked in: the build context is backend/, so ../ml is
# out of reach, and pinning a copy of someone else's folder into this image
# would go stale. compose mounts it at /ml instead, which is where
# app/intelligence.py looks. Without it the API degrades to stored values.

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
