FROM python:3.10-slim

RUN apt-get update && apt-get install -y gcc curl

WORKDIR /app

# Copy the pyproject.toml and poetry.lock files for installing dependencies
COPY pyproject.toml poetry.lock* /app/

# Install Poetry
RUN pip install poetry keyring

# Install dependencies using Poetry with all extras
RUN poetry config virtualenvs.create false \
  && poetry install -E all --no-interaction --no-ansi

# Install gunicorn and uvicorn
RUN pip install gunicorn uvicorn

# Copy the rest of the application code
COPY . /app

# Expose the port
EXPOSE 8000

# Set the command to run the application with Gunicorn
CMD ["gunicorn", "r2r.examples.servers.configurable_pipeline:create_r2r_app", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "8", "--timeout", "0", "--worker-class", "uvicorn.workers.UvicornWorker"]
