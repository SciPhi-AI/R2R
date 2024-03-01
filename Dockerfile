# Use an official Python runtime as a parent image
FROM python:3.9

# Install Poetry
RUN pip install poetry

# Set the working directory in the container
WORKDIR /app

# Copy the pyproject.toml and optionally poetry.lock files
COPY pyproject.toml poetry.lock* /app/

# Disable virtual env creation by Poetry
RUN poetry config virtualenvs.create false

# Add keyring to the project container
RUN pip install keyring

# Install project dependencies
RUN poetry install -E parsing -E eval --no-interaction --no-ansi -vvv

# Copy the rest of your application code
COPY . /app

# Make port 8000 available to the world outside this container
EXPOSE 8000

# Command to run the basic application example
CMD ["uvicorn", "r2r.examples.basic.app:app", "--host", "0.0.0.0", "--port", "8000"]