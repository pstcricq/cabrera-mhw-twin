# Two entry points share this image: the API and the Streamlit dashboard.
# Both read data/exports, so the image carries the committed indicators.
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.9.29 /uv /usr/local/bin/uv

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PATH="/app/.venv/bin:$PATH"

# Dependencies first: they change far less often than the code
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --locked --no-dev --no-install-project

COPY src ./src
COPY dashboard ./dashboard
COPY .streamlit ./.streamlit
COPY data/exports ./data/exports
COPY data/processed/cabrera_mpa.geojson ./data/processed/cabrera_mpa.geojson
RUN uv sync --locked --no-dev

EXPOSE 8000 8501
CMD ["uvicorn", "cabrera_twin.api:app", "--host", "0.0.0.0", "--port", "8000"]
