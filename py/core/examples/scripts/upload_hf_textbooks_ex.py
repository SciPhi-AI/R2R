import asyncio
import os
import uuid

from datasets import load_dataset

from r2r import R2RAsyncClient

batch_size = 64
total_batches = 8
rest_time_in_s = 1


def generate_id(label: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, label)


def remove_file(file_path):
    try:
        os.remove(file_path)
    except Exception as e:
        print(f"Error removing file {file_path}: {e}")


async def process_batch(client, batch):
    results = await client.ingest_files(batch)
    print(f"Submitted {len(results['results'])} files for processing")
    print("results = ", results["results"])
    # Remove the processed files
    for file_path in batch:
        remove_file(file_path)


async def process_dataset(client, dataset, batch_size):
    current_batch = []
    count = 0
    tasks = []

    for example in dataset:
        count += 1
        fname = f"example_{generate_id(example['completion'])}.txt"
        print(f"Streaming {fname} w/ completion {count} ...")

        with open(fname, "w") as f:
            f.write(example["completion"])

        current_batch.append(fname)

        if len(current_batch) == batch_size:
            task = asyncio.create_task(process_batch(client, current_batch))
            tasks.append(task)
            current_batch = []

            if len(tasks) == total_batches:
                await asyncio.gather(*tasks)
                tasks = []  # Reset the tasks list
                # await asyncio.sleep(rest_time_in_s)

    # Process any remaining files in the last batch
    if current_batch:
        await process_batch(client, current_batch)


async def main():
    r2r_url = os.getenv("R2R_API_URL", "http://localhost:7272")
    print(f"Using R2R API at: {r2r_url}")
    client = R2RAsyncClient(r2r_url)

    dataset = load_dataset(
        "SciPhi/textbooks-are-all-you-need-lite", streaming=True
    )["train"]

    print("Submitting batches for processing ...")
    await process_dataset(client, dataset, batch_size)
    print("All batches submitted for processing")


if __name__ == "__main__":
    asyncio.run(main())
