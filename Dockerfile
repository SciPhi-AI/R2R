FROM python:3.10-slim

RUN apt-get update && apt-get install -y gcc

WORKDIR /app

# Copy the pyproject.toml and poetry.lock files for installing dependencies
COPY pyproject.toml poetry.lock* /app/

# Install Poetry
RUN pip install poetry keyring

# Export dependencies to requirements.txt
RUN poetry export --without-hashes --format=requirements.txt --output=requirements.txt -E eval -E sentence_transformers

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Install gunicorn and uvicorn
RUN pip install gunicorn uvicorn

# Copy the rest of the application code
COPY . /app

# Expose the port
EXPOSE 8000

# Set the command to run the application with Gunicorn
CMD ["gunicorn", "r2r.examples.servers.config_pipeline:create_app", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "8", "--timeout", "0", "--worker-class", "uvicorn.workers.UvicornWorker"]