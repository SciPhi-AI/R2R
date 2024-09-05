import os
import time

from r2r import R2RClient

# Our R2R base URL is the URL of our SciPhi deployed R2R server
deployment_url = os.getenv("R2R_DEPLOYMENT_URL")
client = R2RClient(deployment_url)

# We'll make sure that we can connect to the server
health_response = client.health()
print(health_response)

# We'll ingest the data from the data folder
file_paths = ["../web-app/public/data"]
t0 = time.time()
ingest_response = client.ingest_files(
    file_paths=file_paths,
)
t1 = time.time()
print(ingest_response)
print(f"Time taken to ingest: {t1 - t0} seconds")
