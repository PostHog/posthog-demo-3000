FROM python:3.12-slim-bookworm
COPY --from=ghcr.io/astral-sh/uv:0.11.15 /uv /uvx /bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .

EXPOSE 8080

# Initialize the SQLite DB on first start, then serve with Gunicorn
CMD ["sh", "-c", "uv run --no-sync python pop_db.py && uv run --no-sync python dummy_data.py && exec uv run --no-sync gunicorn -b 0.0.0.0:8080 app:app"]
