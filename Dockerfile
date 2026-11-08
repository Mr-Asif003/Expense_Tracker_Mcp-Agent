# syntax=docker/dockerfile:1
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    EXPENSE_DB_PATH=/data/expenses.db

WORKDIR /app

# Install dependencies first for better layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install ".[ui]"

# Run as an unprivileged user; /data holds the SQLite file.
RUN useradd --create-home --uid 1000 app && mkdir /data && chown app /data
USER app
VOLUME ["/data"]

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
  CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8501/_stcore/health', timeout=3)"

# Pass OPENROUTER_API_KEY at runtime (docker run -e / --env-file); never bake it into the image.
CMD ["expense-tracker-ui", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
