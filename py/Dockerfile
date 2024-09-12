FROM python:3.10-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ musl-dev curl libffi-dev gfortran libopenblas-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir poetry

# Copy the pyproject.toml file
RUN mkdir -p /app/py
WORKDIR /app/py
COPY pyproject.toml /app/py

COPY scripts /app/py/scripts

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --extras "core" --no-dev --no-root \
    && pip install --no-cache-dir gunicorn uvicorn

# Final stage to keep the image small
FROM python:3.10-slim

# Install runtime dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the installed packages from the builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

ARG PORT=8000 HOST=0.0.0.0
ENV PORT=$PORT HOST=$HOST
EXPOSE $PORT

# Copy the necessary application files
COPY . /app
COPY core /app/core
COPY r2r /app/r2r
COPY r2r.toml /app/r2r.toml
COPY pyproject.toml /app/pyproject.toml

CMD ["sh", "-c", "uvicorn core.main.app_entry:app --host $HOST --port $PORT"]
