import asyncio
import os
import uuid

import pytest
from fastapi.datastructures import UploadFile

from r2r import (
    Document,
    GenerationConfig,
    KVLoggingSingleton,
    R2RConfig,
    R2REngine,
    R2RPipeFactory,
    R2RPipelineFactory,
    R2RProviderFactory,
    VectorSearchSettings,
    generate_id_from_label,
)


@pytest.fixture(scope="session", autouse=True)
def event_loop_policy():
    asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())


@pytest.fixture(scope="function", autouse=True)
async def cleanup_tasks():
    yield
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    [task.cancel() for task in tasks]
    await asyncio.gather(*tasks, return_exceptions=True)


@pytest.fixture(scope="function")
def app(request):
    config = R2RConfig.from_toml()
    config.logging.provider = "postgres"
    config.logging.logging_path = uuid.uuid4().hex
    print("config.logging.logging_path = ", config.logging.logging_path)

    config.database.provider = "postgres"
    config.database.extra_fields["vecs_collection"] = (
        config.logging.logging_path
    )
    try:
        providers = R2RProviderFactory(config).create_providers()
        pipes = R2RPipeFactory(config, providers).create_pipes()
        pipelines = R2RPipelineFactory(config, pipes).create_pipelines()

        r2r = R2REngine(
            config=config,
            providers=providers,
            pipelines=pipelines,
            agents={},
        )

        try:
            if os.path.exists(config.logging.logging_path):
                os.remove(config.logging.logging_path)

            print(
                "config.logging.logging_path = ", config.logging.logging_path
            )
            KVLoggingSingleton.configure(config.logging)
        except:
            KVLoggingSingleton._config.logging_path = (
                config.logging.logging_path
            )

        yield r2r
    finally:
        if os.path.exists(config.logging.logging_path):
            os.remove(config.logging.logging_path)


@pytest.fixture
def logging_connection():
    return KVLoggingSingleton()


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_txt_document(app, logging_connection):
    await app.aingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_1"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_txt_file(app, logging_connection):
    # Prepare the test data
    metadata = {"author": "John Doe"}
    files = [
        UploadFile(
            filename="test.txt",
            file=open(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "r2r",
                    "examples",
                    "data",
                    "test.txt",
                ),
                "rb",
            ),
        )
    ]
    # Set file size manually
    for file in files:
        file.file.seek(0, 2)  # Move to the end of the file
        file.size = file.file.tell()  # Get the file size
        file.file.seek(0)  # Move back to the start of the file

    await app.aingest_files(metadatas=[metadata], files=files)


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_search_txt_file(app, logging_connection):

    # Convert metadata to JSON string
    run_info = await logging_connection.get_run_info(log_type_filter="search")
    print("a", len(run_info))

    # Prepare the test data
    metadata = {}
    files = [
        UploadFile(
            filename="aristotle.txt",
            file=open(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "r2r",
                    "examples",
                    "data",
                    "aristotle.txt",
                ),
                "rb",
            ),
        ),
    ]

    # Set file size manually
    for file in files:
        file.file.seek(0, 2)  # Move to the end of the file
        file.size = file.file.tell()  # Get the file size
        file.file.seek(0)  # Move back to the start of the file

    # Convert metadata to JSON string
    run_info = await logging_connection.get_run_info(log_type_filter="search")
    print("b", len(run_info))

    await app.aingest_files(metadatas=[metadata], files=files)

    run_info = await logging_connection.get_run_info(log_type_filter="search")
    print("c", len(run_info))

    search_results = await app.asearch("who was aristotle?")
    assert len(search_results["vector_search_results"]) == 10
    assert (
        "was an Ancient Greek philosopher and polymath"
        in search_results["vector_search_results"][0]["metadata"]["text"]
    )

    search_results = await app.asearch(
        "who was aristotle?",
        vector_search_settings=VectorSearchSettings(search_limit=20),
    )
    assert len(search_results["vector_search_results"]) == 20
    assert (
        "was an Ancient Greek philosopher and polymath"
        in search_results["vector_search_results"][0]["metadata"]["text"]
    )
    run_info = await logging_connection.get_run_info(log_type_filter="search")
    print("d", len(run_info))
    assert len(run_info) == 2, f"Expected 2 runs, but got {len(run_info)}"

    logs = await logging_connection.get_logs(
        [run.run_id for run in run_info], 100
    )
    assert len(logs) == 6, f"Expected 6 logs, but got {len(logs)}"

    ## test stream
    response = await app.arag(
        query="Who was aristotle?",
        rag_generation_config=GenerationConfig(
            **{"model": "gpt-3.5-turbo", "stream": True}
        ),
    )
    collector = ""
    async for chunk in response:
        collector += chunk
    assert "Aristotle" in collector
    assert "Greek" in collector
    assert "philosopher" in collector
    assert "polymath" in collector
    assert "Ancient" in collector


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_search_then_delete(app, logging_connection):
    # Ingest a document
    await app.aingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_1"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )

    # Search for the document
    search_results = await app.asearch("who was aristotle?")

    # Verify that the search results are not empty
    assert (
        len(search_results["vector_search_results"]) > 0
    ), "Expected search results, but got none"
    assert (
        search_results["vector_search_results"][0]["metadata"]["text"]
        == "The quick brown fox jumps over the lazy dog."
    )

    # Delete the document
    delete_result = await app.adelete(filters={"author": {"$eq": "John Doe"}})

    # Verify the deletion was successful
    assert (
        len(delete_result) > 0
    ), f"Expected at least one document to be deleted, but got {delete_result}"

    # Search for the document again
    search_results_2 = await app.asearch("who was aristotle?")

    # Verify that the search results are empty
    assert (
        len(search_results_2["vector_search_results"]) == 0
    ), f"Expected no search results, but got {search_results_2['vector_search_results']}"


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_user_documents(app, logging_connection):
    user_id_0 = generate_id_from_label("user_0")
    user_id_1 = generate_id_from_label("user_1")
    doc_id_0 = generate_id_from_label("doc_01")
    doc_id_1 = generate_id_from_label("doc_11")

    await app.aingest_documents(
        [
            Document(
                id=doc_id_0,
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe", "user_id": user_id_0},
            ),
            Document(
                id=doc_id_1,
                data="The lazy dog jumps over the quick brown fox.",
                type="txt",
                metadata={"author": "John Doe", "user_id": user_id_1},
            ),
        ]
    )
    user_id_results = await app.ausers_overview([user_id_0, user_id_1])
    assert set([stats.user_id for stats in user_id_results]) == set(
        [user_id_0, user_id_1]
    ), f"Expected user ids {user_id_0} and {user_id_1}, but got {user_id_results}"

    user_0_docs = await app.adocuments_overview(user_ids=[user_id_0])
    user_1_docs = await app.adocuments_overview(user_ids=[user_id_1])

    assert (
        len(user_0_docs) == 1
    ), f"Expected 1 document for user {user_id_0}, but got {len(user_0_docs)}"
    assert (
        len(user_1_docs) == 1
    ), f"Expected 1 document for user {user_id_1}, but got {len(user_1_docs)}"
    assert (
        user_0_docs[0].document_id == doc_id_0
    ), f"Expected document id {doc_id_0} for user {user_id_0}, but got {user_0_docs[0].document_id}"
    assert (
        user_1_docs[0].document_id == doc_id_1
    ), f"Expected document id {doc_id_1} for user {user_id_1}, but got {user_1_docs[0].document_id}"

    # Clean up
    delete_result = await app.adelete(
        filters={"document_id": {"$in": [str(doc_id_0), str(doc_id_1)]}}
    )
    assert (
        len(delete_result) == 2
    ), f"Expected 2 documents to be deleted, but got {len(delete_result)}"


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_delete_by_id(app, logging_connection):
    doc_id = generate_id_from_label("doc_1")
    await app.aingest_documents(
        [
            Document(
                id=doc_id,
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )
    search_results = await app.asearch("who was aristotle?")

    assert len(search_results["vector_search_results"]) > 0
    delete_result = await app.adelete(
        filters={"document_id": {"$eq": str(doc_id)}}
    )
    assert (
        len(delete_result) == 1
    ), f"Expected 1 document to be deleted, but got {len(delete_result)}"
    search_results = await app.asearch("who was aristotle?")
    assert len(search_results["vector_search_results"]) == 0


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_double_ingest(app, logging_connection):
    await app.aingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_1"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )
    search_results = await app.asearch("who was aristotle?")

    assert len(search_results["vector_search_results"]) == 1
    with pytest.raises(Exception):
        try:
            await app.aingest_documents(
                [
                    Document(
                        id=generate_id_from_label("doc_1"),
                        data="The quick brown fox jumps over the lazy dog.",
                        type="txt",
                        metadata={"author": "John Doe"},
                    ),
                ]
            )
        except asyncio.CancelledError:
            pass


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_search_then_delete(app, logging_connection):
    # Ingest a document
    await app.aingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_1"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )

    # Search for the document
    search_results = await app.asearch("who was aristotle?")

    # Verify that the search results are not empty
    assert (
        len(search_results["vector_search_results"]) > 0
    ), "Expected search results, but got none"
    assert (
        search_results["vector_search_results"][0]["metadata"]["text"]
        == "The quick brown fox jumps over the lazy dog."
    )

    # Delete the document
    delete_result = await app.adelete(filters={"author": {"$eq": "John Doe"}})

    # Verify the deletion was successful
    assert (
        len(delete_result) > 0
    ), f"Expected at least one document to be deleted, but got {delete_result}"

    # Search for the document again
    search_results_2 = await app.asearch("who was aristotle?")

    # Verify that the search results are empty
    assert (
        len(search_results_2["vector_search_results"]) == 0
    ), f"Expected no search results, but got {search_results_2['vector_search_results']}"


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_user_documents(app, logging_connection):
    user_id_0 = generate_id_from_label("user_0")
    user_id_1 = generate_id_from_label("user_1")
    doc_id_0 = generate_id_from_label("doc_01")
    doc_id_1 = generate_id_from_label("doc_11")

    await app.aingest_documents(
        [
            Document(
                id=doc_id_0,
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe", "user_id": user_id_0},
            ),
            Document(
                id=doc_id_1,
                data="The lazy dog jumps over the quick brown fox.",
                type="txt",
                metadata={"author": "John Doe", "user_id": user_id_1},
            ),
        ]
    )
    user_id_results = await app.ausers_overview([user_id_0, user_id_1])
    assert set([stats.user_id for stats in user_id_results]) == set(
        [user_id_0, user_id_1]
    ), f"Expected user ids {user_id_0} and {user_id_1}, but got {user_id_results}"

    user_0_docs = await app.adocuments_overview(user_ids=[user_id_0])
    user_1_docs = await app.adocuments_overview(user_ids=[user_id_1])

    assert (
        len(user_0_docs) == 1
    ), f"Expected 1 document for user {user_id_0}, but got {len(user_0_docs)}"
    assert (
        len(user_1_docs) == 1
    ), f"Expected 1 document for user {user_id_1}, but got {len(user_1_docs)}"
    assert (
        user_0_docs[0].document_id == doc_id_0
    ), f"Expected document id {doc_id_0} for user {user_id_0}, but got {user_0_docs[0].document_id}"
    assert (
        user_1_docs[0].document_id == doc_id_1
    ), f"Expected document id {doc_id_1} for user {user_id_1}, but got {user_1_docs[0].document_id}"

    # Clean up
    delete_result = await app.adelete(
        filters={"document_id": {"$in": [str(doc_id_0), str(doc_id_1)]}}
    )
    assert (
        len(delete_result) == 112
    ), f"Expected 112 chunks to be deleted, but got {len(delete_result)}"


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_delete_by_id(app, logging_connection):
    doc_id = generate_id_from_label("doc_1")
    await app.aingest_documents(
        [
            Document(
                id=doc_id,
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )
    search_results = await app.asearch("who was aristotle?")

    assert len(search_results["vector_search_results"]) > 0
    delete_result = await app.adelete(
        filters={"document_id": {"$eq": str(doc_id)}}
    )
    assert (
        len(delete_result) > 0
    ), f"Expected at least one document to be deleted, but got {delete_result}"
    search_results = await app.asearch("who was aristotle?")
    assert len(search_results["vector_search_results"]) == 0
