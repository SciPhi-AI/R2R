#!/bin/bash

# Check if HATCHET_CLIENT_TOKEN is set, if not read it from the API key file
if [ -z "${HATCHET_CLIENT_TOKEN}" ]; then
  export HATCHET_CLIENT_TOKEN=$(cat /hatchet_api_key/api_key.txt)
fi

# Start the application
exec uvicorn core.main.app_entry:app --host ${R2R_HOST} --port ${R2R_PORT}
