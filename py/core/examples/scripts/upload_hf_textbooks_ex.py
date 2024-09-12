import os
import time
import uuid

from datasets import load_dataset

from r2r import R2RClient


def generate_id_from_label(label: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, label)


def upload_batch(client, file_paths):
    print(f"Uploading batch of {len(file_paths)} files")
    response = client.ingest_files(file_paths=file_paths)
    print(response)
    for fname in file_paths:
        os.remove(fname)


if __name__ == "__main__":
    r2r_url = os.getenv("R2R_API_URL", "http://localhost:7272")
    print(f"Using R2R API at: {r2r_url}")
    client = R2RClient(r2r_url)

    # Load the dataset
    dataset = load_dataset(
        "SciPhi/textbooks-are-all-you-need-lite", streaming=True
    )

    # Get the train split (or any other split you want to use)
    stream = dataset["train"]

    batch_size = 16
    current_batch = []

    # Iterate over the stream and batch the files
    count = 0
    for example in stream:
        count += 1
        fname = f"example_{generate_id_from_label(example['completion'])}.txt"
        print(f"Streaming {fname} w/ completion {count} ...")
        with open(fname, "w") as f:
            f.write(example["completion"])
        current_batch.append(fname)

        if len(current_batch) >= batch_size:
            upload_batch(client, current_batch)
            current_batch = []
            time.sleep(1)  # sleep for 1 second between batches

    # Upload any remaining files in the last batch
    if current_batch:
        upload_batch(client, current_batch)
