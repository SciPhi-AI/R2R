import time

from r2r import R2RClient

# Our R2R base URL is the URL of our SciPhi deployed R2R server
client = R2RClient("YOUR_SCIPHI_DEPLOYMENT_URL")

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
