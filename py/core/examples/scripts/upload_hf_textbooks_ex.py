import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import aiofiles
from datasets import load_dataset

from r2r import R2RClient

batch_size = 128
rest_time_in_s = 5


def generate_id(label: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, label)


async def upload_batch(client, file_paths, executor):
    print(f"Uploading batch of {len(file_paths)} files")
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(
            executor, client.ingest_files, file_paths
        )
        print(response)
    except Exception as e:
        print(f"Error uploading batch: {e}")
    finally:
        await asyncio.gather(*(remove_file(fname) for fname in file_paths))


async def remove_file(file_path):
    try:
        os.remove(file_path)
    except Exception as e:
        print(f"Error removing file {file_path}: {e}")


async def process_dataset(client, dataset, batch_size, executor):
    current_batch = []
    count = 0

    for example in dataset:
        count += 1
        fname = f"example_{generate_id(example['completion'])}.txt"
        print(f"Streaming {fname} w/ completion {count} ...")

        async with aiofiles.open(fname, "w") as f:
            await f.write(example["completion"])

        current_batch.append(fname)

        if len(current_batch) >= batch_size:
            asyncio.create_task(
                upload_batch(client, current_batch.copy(), executor)
            )
            current_batch.clear()
            await asyncio.sleep(rest_time_in_s)

    if current_batch:
        asyncio.create_task(
            upload_batch(client, current_batch.copy(), executor)
        )


async def main():
    r2r_url = os.getenv("R2R_API_URL", "http://localhost:7272")
    print(f"Using R2R API at: {r2r_url}")
    client = R2RClient(r2r_url)

    dataset = load_dataset(
        "SciPhi/textbooks-are-all-you-need-lite", streaming=True
    )["train"]

    with ThreadPoolExecutor() as executor:
        print("Submitting batches for processing ...")
        await process_dataset(client, dataset, batch_size, executor)
        print("All batches submitted for processing")


if __name__ == "__main__":
    asyncio.run(main())
