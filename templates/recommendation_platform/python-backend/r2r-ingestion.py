import csv
import os

from r2r import R2RClient

# Initialize the R2RClient
client = R2RClient("YOUR_SCIPHI_DEPLOYMENT_URL")

# Check server health
health_response = client.health()
if health_response["response"] != "ok":
    raise Exception("Unable to connect to the R2R server.")

# Path to the original CSV file from DataSF
input_csv_path = (
    "sfpopos/web-app/public/data/Privately_Owned_Public_Open_Spaces_20240809.csv"
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

        # Ingest the temporary file using the R2R client
        client.ingest_files(
            [temp_filename], ingestion_config={"provider": "r2r", "chunk_size": 2048}
        )

        os.remove(temp_filename)

print("All rows have been processed and ingested.")
