import asyncio
import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import aiofiles
from datasets import load_dataset

from r2r import R2RClient


def generate_id(label: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, label)


async def upload_batch(client, file_paths, executor):
    print(f"Uploading batch of {len(file_paths)} files")
    loop = asyncio.get_event_loop()
    try:
        # Assuming ingest_files is a blocking I/O operation
        response = await loop.run_in_executor(
            executor, client.ingest_files, file_paths
        )
        print(response)
    except Exception as e:
        print(f"Error uploading batch: {e}")
    finally:
        # Remove files asynchronously
        await asyncio.gather(*(remove_file(fname) for fname in file_paths))


async def remove_file(file_path):
    try:
        os.remove(file_path)
    except Exception as e:
        print(f"Error removing file {file_path}: {e}")


async def process_dataset(client, dataset, batch_size, executor, semaphore):
    current_batch = []
    count = 0

    for example in dataset:
        count += 1
        fname = f"example_{generate_id(example['completion'])}.txt"
        print(f"Streaming {fname} w/ completion {count} ...")

        # Asynchronously write to file
        async with aiofiles.open(fname, "w") as f:
            await f.write(example["completion"])

        current_batch.append(fname)

        if len(current_batch) >= batch_size:
            # Acquire semaphore before launching a new upload task
            await semaphore.acquire()
            asyncio.create_task(
                upload_and_release(
                    semaphore,
                    upload_batch,
                    client,
                    current_batch.copy(),
                    executor,
                )
            )
            current_batch.clear()

    # Upload any remaining files
    if current_batch:
        await semaphore.acquire()
        asyncio.create_task(
            upload_and_release(
                semaphore, upload_batch, client, current_batch.copy(), executor
            )
        )


async def upload_and_release(semaphore, upload_func, client, batch, executor):
    try:
        await upload_func(client, batch, executor)
    finally:
        semaphore.release()


async def main():
    r2r_url = os.getenv("R2R_API_URL", "http://localhost:7272")
    print(f"Using R2R API at: {r2r_url}")
    client = R2RClient(r2r_url)

    # Load the dataset
    dataset = load_dataset(
        "SciPhi/textbooks-are-all-you-need-lite", streaming=True
    )["train"]

    batch_size = 64
    max_concurrent_uploads = 10  # Adjust based on your system/API limits
    semaphore = asyncio.Semaphore(max_concurrent_uploads)

    # Use a ThreadPoolExecutor for blocking I/O operations
    with ThreadPoolExecutor(max_workers=max_concurrent_uploads) as executor:
        await process_dataset(client, dataset, batch_size, executor, semaphore)

        # Wait for all upload tasks to complete
        # This ensures that all tasks have been launched
        # and then waits for them to finish
        await asyncio.sleep(0.1)  # Let asyncio schedule the tasks

        # Optionally, gather all pending tasks
        pending = [
            task
            for task in asyncio.all_tasks()
            if task is not asyncio.current_task()
        ]
        if pending:
            await asyncio.gather(*pending)


if __name__ == "__main__":
    asyncio.run(main())
