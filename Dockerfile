# Fishing Atlas — Flask + SQLite, served by gunicorn.
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install dependencies first for better layer caching.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# App source.
COPY . .

# Persistent data (SQLite db + uploaded photos) lives on a mounted volume.
RUN mkdir -p /app/instance /app/app/static/uploads

EXPOSE 5000

# Entrypoint creates tables, optionally seeds, then starts gunicorn.
RUN chmod +x /app/docker-entrypoint.sh
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "wsgi:app"]
