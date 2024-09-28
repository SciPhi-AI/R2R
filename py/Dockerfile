FROM python:3.10-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ musl-dev curl libffi-dev gfortran libopenblas-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

    RUN pip install --no-cache-dir poetry

# Add Rust to PATH
ENV PATH="/root/.cargo/bin:${PATH}"

RUN mkdir -p /app/py
WORKDIR /app/py
COPY pyproject.toml /app/py/pyproject.toml

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --extras "core ingestion-bundle" --no-dev --no-root \
    && pip install --no-cache-dir gunicorn uvicorn

# Create the final image
FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Expose the port and set environment variables
ARG PORT=8000 HOST=0.0.0.0
ENV PORT=$PORT HOST=$HOST
EXPOSE $PORT

COPY . /app
# Copy the application and config
COPY core /app/core
COPY r2r /app/r2r
COPY shared /app/shared
COPY r2r.toml /app/r2r.toml
COPY pyproject.toml /app/pyproject.toml

# Run the application
CMD ["sh", "-c", "uvicorn core.main.app_entry:app --host $HOST --port $PORT"]
