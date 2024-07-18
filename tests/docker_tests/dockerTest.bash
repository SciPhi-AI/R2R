#!/bin/bash

# This script runs tests to verify the functionality of the Docker container for both local and cloud providers.
# To run: bash dockerTest.bash

set -eo pipefail

[ "$DEBUG" ] && set -x

# Set current working directory to the directory of the script
cd "$(dirname "$0")"

dockerImage="emrgntcmplxty/r2r:latest"

# Function to check if a command exists
command_exists() {
  command -v "$1" >/dev/null 2>&1
}

# Test for Docs Instance 1
test_instance_1() {
  echo "Running test for Docs Instance 1..."

  # Check if OPENAI_API_KEY is set
  if [ -z "$OPENAI_API_KEY" ]; then
    echo "Error: OPENAI_API_KEY is not set."
    return 1
  fi

  # Check if the Docker image exists
  if ! docker inspect "$dockerImage" &> /dev/null; then
    echo "Image $dockerImage does not exist!"
    return 1
  fi

  # Run the Docker container
  cid="$(docker run -d \
    --name r2r_test \
    --add-host=host.docker.internal:host-gateway \
    -p 8000:8000 \
    -e OPENAI_API_KEY=$OPENAI_API_KEY \
    $dockerImage)"

  # Remove the container afterwards
  trap "docker rm -vf $cid > /dev/null" EXIT

  # Check if the container is running
  if [ "$(docker inspect -f '{{.State.Running}}' $cid)" != "true" ]; then
    echo "Error: r2r_test container is not running."
    return 1
  fi

  # Check if the network socket is available
  if ! nc -zv 127.0.0.1 8000; then
    echo "Error: Port 8000 is not available."
    return 1
  fi

  echo "Test for Docs Instance 1 passed successfully."

  # Stop and remove the container
  docker stop $cid
  docker rm $cid
}

# Test for Docs Instance 2
test_instance_2() {
  echo "Running test for Docs Instance 2..."

  # Check if the Docker image exists
  if ! docker inspect "$dockerImage" &> /dev/null; then
    echo "Image $dockerImage does not exist!"
    return 1
  fi

  # Check if Ollama is installed
  if ! command_exists ollama; then
    echo "Error: Ollama is not installed. Please install Ollama to proceed."
    return 1
  fi

  # Start the Ollama service
  ollama serve &

  # Wait for Ollama service to start
  sleep 10

  # Run the Docker container
  cid="$(docker run -d \
    --name r2r_test \
    --add-host=host.docker.internal:host-gateway \
    -p 8000:8000 \
    -e OLLAMA_API_BASE=http://host.docker.internal:11434 \
    -e CONFIG_OPTION=local_ollama \
    $dockerImage)"

  # Remove the container afterwards
  trap "docker rm -vf $cid > /dev/null" EXIT

  # Check if the container is running
  if [ "$(docker inspect -f '{{.State.Running}}' $cid)" != "true" ]; then
    echo "Error: r2r_test container is not running."
    return 1
  fi

  # Check if the network socket is available
  if ! nc -zv 127.0.0.1 8000; then
    echo "Error: Port 8000 is not available."
    return 1
  fi

  echo "Test for Docs Instance 2 passed successfully."
}

# Run both tests
test_instance_1
test1_status=$?

test_instance_2
test2_status=$?

# Exit with an error code if any test failed
if [ $test1_status -ne 0 ] || [ $test2_status -ne 0 ]; then
  echo "One or more tests failed."
  exit 1
fi

echo "All tests passed successfully."