FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ musl-dev curl libffi-dev gfortran libopenblas-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the pyproject.toml and poetry.lock files for installing dependencies
COPY pyproject.toml poetry.lock* /app/

# Install Poetry and configure it to create a virtual environment
RUN pip install poetry && poetry config virtualenvs.create false && poetry install --no-dev

# Copy the rest of the application code
COPY . /app

# Install additional dependencies
RUN poetry run pip install --no-cache-dir uvicorn fastapi

# Expose the port
EXPOSE 8000

# Set environment variable to indicate Docker environment
ENV DOCKER_ENV=true

# Set the command to run the application
CMD ["poetry", "run", "python", "-m", "r2r.examples.quickstart", "serve"]
