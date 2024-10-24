import io
import uuid

import pytest


@pytest.mark.asyncio
async def test_store_and_retrieve_file(postgres_db_provider):
    document_id = uuid.uuid4()
    file_name = "test_file.txt"
    file_content = io.BytesIO(b"Test file content")
    file_type = "text/plain"

    await postgres_db_provider.store_file(
        document_id, file_name, file_content, file_type
    )
    retrieved_file = await postgres_db_provider.retrieve_file(document_id)

    assert retrieved_file is not None
    assert retrieved_file[0] == file_name
    assert retrieved_file[1].read() == b"Test file content"
    assert retrieved_file[2] == len(b"Test file content")


@pytest.mark.asyncio
async def test_delete_file(postgres_db_provider):
    document_id = uuid.uuid4()
    file_name = "test_file.txt"
    file_content = io.BytesIO(b"Test file content")
    file_type = "text/plain"

    await postgres_db_provider.store_file(
        document_id, file_name, file_content, file_type
    )
    deleted = await postgres_db_provider.delete_file(document_id)

    assert deleted is True
    with pytest.raises(Exception):
        await postgres_db_provider.retrieve_file(document_id)


@pytest.mark.asyncio
async def test_get_files_overview(postgres_db_provider):
    document_ids = [uuid.uuid4() for _ in range(5)]
    file_names = [f"test_file_{i}.txt" for i in range(5)]
    file_contents = [
        io.BytesIO(f"Test file content {i}".encode()) for i in range(5)
    ]
    file_type = "text/plain"

    for document_id, file_name, file_content in zip(
        document_ids, file_names, file_contents
    ):
        await postgres_db_provider.store_file(
            document_id, file_name, file_content, file_type
        )

    files_overview = await postgres_db_provider.get_files_overview(limit=3)

    assert len(files_overview) == 3
    assert all(file["document_id"] in document_ids for file in files_overview)
    assert all(file["file_name"] in file_names for file in files_overview)

    filtered_files_overview = await postgres_db_provider.get_files_overview(
        filter_document_ids=[document_ids[0], document_ids[1]],
        filter_file_names=[file_names[0]],
    )

    assert len(filtered_files_overview) == 1
    assert filtered_files_overview[0]["document_id"] == document_ids[0]
    assert filtered_files_overview[0]["file_name"] == file_names[0]
