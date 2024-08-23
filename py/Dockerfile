FROM python:3.10-slim AS builder

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ musl-dev curl libffi-dev gfortran libopenblas-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/* \
    && curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app

RUN pip install --no-cache-dir poetry

# Copy the entire project into the container
COPY . /app

# Ensure that the working directory is set to /app/py
WORKDIR /app/py
COPY scripts /app/py/scripts

# Install dependencies
RUN poetry config virtualenvs.create false \
    && poetry install --extras "core" --no-dev --no-root \
    && pip install --no-cache-dir gunicorn uvicorn \
    && poetry run python scripts/download_nltk_data.py



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
COPY --from=builder /root/nltk_data /root/nltk_data

# Copy the necessary application files
COPY core /app/core
COPY r2r /app/r2r
COPY r2r.toml /app/r2r.toml
COPY pyproject.toml /app/pyproject.toml

ARG PORT=8000
ARG HOST=0.0.0.0
ENV PORT=$PORT HOST=$HOST
EXPOSE $PORT

CMD ["sh", "-c", "uvicorn core.main.app_entry:app --host $HOST --port $PORT"]
