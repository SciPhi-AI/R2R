import csv
import os

from r2r import R2RClient

# Our R2R base URL is the URL of our SciPhi deployed R2R server
deployment_url = os.getenv("R2R_DEPLOYMENT_URL")
client = R2RClient(deployment_url)

# Check server health
health_response = client.health()
print(health_response)

# Path to the original CSV file from DataSF
input_csv_path = (
    "../web-app/public/data/Privately_Owned_Public_Open_Spaces_20240809.csv"
)

# Read the CSV file and process each row as a separate file
with open(input_csv_path, "r") as csvfile:
    csvreader = csv.reader(csvfile)

    header = next(csvreader)
    name_index = header.index("NAME")

    for row in csvreader:
        row_name = row[name_index].replace(" ", "_").replace("/", "-")
        temp_filename = f"{row_name}.txt"

        with open(temp_filename, "w") as temp_txtfile:
            for key, value in zip(header, row):
                temp_txtfile.write(f"{key}: {value}\n")

        # Ingest the temporary file using the R2R client with a custom chunk size
        client.ingest_files(
            [temp_filename], ingestion_config={"provider": "r2r", "chunk_size": 4096}
        )

        os.remove(temp_filename)

print("All rows have been processed and ingested.")
