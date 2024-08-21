FROM python:3.10-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ musl-dev curl libffi-dev gfortran libopenblas-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

RUN pip install --no-cache-dir poetry

# Copy the dependencies files
COPY py/pyproject.toml py/poetry.lock* ./

# Install the dependencies, including gunicorn and uvicorn
RUN poetry config virtualenvs.create false \
    && poetry install --extras "core" --no-dev --no-root \
    && pip install --no-cache-dir gunicorn uvicorn

# Create the final image
FROM python:3.10-slim

# Install healthcheck dependency
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app/py

# Copy the installed packages from the builder
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy the application and config
COPY py/core /app/py/core
COPY r2r.toml /app/r2r.toml
COPY py/pyproject.toml /app/py/pyproject.toml

ENV PYTHONPATH="${PYTHONPATH}:/app/py"

# Expose the port
ARG PORT=8000
ARG HOST=0.0.0.0
ENV PORT=$PORT HOST=$HOST
EXPOSE $PORT

# Run the application
CMD ["sh", "-c", "uvicorn core.main.app_entry:app --host $HOST --port $PORT"]
