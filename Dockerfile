FROM python:3.9-slim

RUN apt-get update && apt-get install -y gcc python3-dev

WORKDIR /app

# Install Poetry and keyring together to reduce layers
RUN pip install poetry keyring gunicorn

# Copy only files necessary for installing dependencies to leverage Docker cache
COPY pyproject.toml poetry.lock* /app/

# Disable virtualenv creation by Poetry, install dependencies
RUN poetry install -E parsing -E eval --no-interaction --no-ansi -vvv

# Copy the rest of the application code
COPY . /app

EXPOSE 8000

CMD ["gunicorn", "src.app:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "8", "--timeout", "0", "--worker-class", "uvicorn.workers.UvicornWorker"]