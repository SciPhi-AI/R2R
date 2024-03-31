# Use a slimmer base image if possible
FROM python:3.9

WORKDIR /app

# Install Poetry and keyring together to reduce layers
RUN pip install poetry keyring

# Copy only files necessary for installing dependencies to leverage Docker cache
COPY pyproject.toml poetry.lock* /app/

# Disable virtualenv creation by Poetry, install dependencies
RUN poetry install -E parsing -E eval --no-interaction --no-ansi -vvv

# Copy the rest of the application code
COPY . /app

EXPOSE 8000

CMD ["uvicorn", "r2r.examples.basic.app:app", "--host", "0.0.0.0", "--port", "8000"]