FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app/src:/app

WORKDIR /app

COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY apps/api/app ./app
COPY apps/api/src ./src
COPY apps/api/alembic.ini ./alembic.ini
COPY apps/api/migrations ./migrations
COPY scripts/bootstrap_model.py ./scripts/bootstrap_model.py

EXPOSE 8000

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

HEALTHCHECK --interval=10s --timeout=3s --retries=5 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live', timeout=2)"

CMD ["sh", "-c", "PYTHONPATH=/app/src alembic upgrade head && python scripts/bootstrap_model.py && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
