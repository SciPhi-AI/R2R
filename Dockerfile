FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc g++ musl-dev curl libffi-dev gfortran libopenblas-dev \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the pyproject.toml and poetry.lock files for installing dependencies
COPY pyproject.toml poetry.lock* /app/

# Install Poetry and dependencies
RUN pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev

# Copy the rest of the application code
COPY . /app

# Install gunicorn and uvicorn
RUN pip install --no-cache-dir gunicorn uvicorn

# Expose the port
EXPOSE 8000

# Run the application using Poetry
CMD ["poetry", "run", "uvicorn", "r2r.examples.quickstart_entry:app", "--host", "0.0.0.0", "--port", "8000"]
