FROM python:3.10-slim

RUN apt-get update && apt-get install -y gcc

WORKDIR /app

# Copy the pyproject.toml and poetry.lock files for installing dependencies
COPY pyproject.toml poetry.lock* /app/

# Install Poetry
RUN pip install poetry keyring

# Export dependencies to requirements.txt
RUN poetry export --without-hashes --format=requirements.txt --output=requirements.txt -E eval -E parsing

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Install gunicorn and uvicorn
RUN pip install gunicorn uvicorn

# Copy the rest of the application code
COPY . /app

EXPOSE 8000

CMD ["gunicorn", "r2r.examples.servers.basic_pipeline:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "8", "--timeout", "0", "--worker-class", "uvicorn.workers.UvicornWorker"]
# FROM python:3.9

# RUN apt-get update && apt-get install -y gcc

# WORKDIR /app

# # Install Poetry and keyring together to reduce layers
# RUN pip install poetry keyring gunicorn uvicorn

# # Copy only files necessary for installing dependencies to leverage Docker cache
# COPY pyproject.toml poetry.lock* /app/

# # Disable virtualenv creation by Poetry, install dependencies
# RUN poetry install -E parsing -E eval --no-interaction --no-ansi -vvv

# # Copy the rest of the application code
# COPY . /app

# EXPOSE 8000

# CMD ["gunicorn", "r2r.examples.servers.basic_pipeline:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "8", "--timeout", "0", "--worker-class", "uvicorn.workers.UvicornWorker"]