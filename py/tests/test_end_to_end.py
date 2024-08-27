import asyncio
import os
import uuid

import pytest
from fastapi.datastructures import UploadFile

from core import (
    Document,
    DocumentInfo,
    DocumentStatus,
    DocumentType,
    GenerationConfig,
    R2RConfig,
    R2REngine,
    R2RPipeFactory,
    R2RPipelineFactory,
    R2RProviderFactory,
    RunLoggingSingleton,
    UserResponse,
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
    config.logging.provider = "local"
    config.logging.logging_path = uuid.uuid4().hex

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

            RunLoggingSingleton.configure(config.logging)
        except:
            RunLoggingSingleton._config.logging_path = (
                config.logging.logging_path
            )

        yield r2r
    finally:
        if os.path.exists(config.logging.logging_path):
            os.remove(config.logging.logging_path)


@pytest.fixture
def logging_connection():
    return RunLoggingSingleton()


@pytest.fixture
def user():
    return UserResponse(
        id=generate_id_from_label("user"),
        email="test@test.com",
        hashed_password="test",
    )


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_txt_document(app, logging_connection):
    user_id = uuid.uuid4()
    group_id = uuid.uuid4()
    doc_id = uuid.uuid4()
    await app.aingest_documents(
        [
            Document(
                id=doc_id,
                group_ids=[group_id],
                user_id=user_id,
                data="The quick brown fox jumps over the lazy dog.",
                type=DocumentType.TXT,
                metadata={"author": "John Doe"},
            ),
        ]
    )

    # Verify the document was ingested correctly
    docs_overview = await app.adocuments_overview(document_ids=[doc_id])
    assert len(docs_overview) == 1
    assert docs_overview[0].id == doc_id
    assert docs_overview[0].group_ids == [group_id]
    assert docs_overview[0].user_id == user_id
    assert docs_overview[0].type == DocumentType.TXT
    assert docs_overview[0].metadata["author"] == "John Doe"
    assert docs_overview[0].ingestion_status == DocumentStatus.SUCCESS


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_txt_file(app, user):
    # Prepare the test data
    metadata = {"author": "John Doe"}
    files = [
        UploadFile(
            filename="test.txt",
            file=open(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "core",
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
    await app.aingest_files(metadatas=[metadata], files=files, user=user)


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_search_txt_file(app, user, logging_connection):

    # Convert metadata to JSON string
    run_info = await logging_connection.get_info_logs(run_type_filter="search")

    # Prepare the test data
    metadata = {}
    files = [
        UploadFile(
            filename="aristotle.txt",
            file=open(
                os.path.join(
                    os.path.dirname(__file__),
                    "..",
                    "core",
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
    run_info = await logging_connection.get_info_logs(run_type_filter="search")

    ingestion_result = await app.aingest_files(
        files=files, user=user, metadatas=[metadata]
    )

    run_info = await logging_connection.get_info_logs(run_type_filter="search")

    search_results = await app.asearch("who was aristotle?")
    print("search results = ", search_results["vector_search_results"][0])
    assert len(search_results["vector_search_results"]) == 10
    assert (
        "was an Ancient Greek philosopher and polymath"
        in search_results["vector_search_results"][0]["text"]
    )

    search_results = await app.asearch(
        "who was aristotle?",
        vector_search_settings=VectorSearchSettings(search_limit=20),
    )
    assert len(search_results["vector_search_results"]) == 20
    assert (
        "was an Ancient Greek philosopher and polymath"
        in search_results["vector_search_results"][0]["text"]
    )
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
async def test_double_ingest(app, logging_connection):
    await app.aingest_documents(
        [
            Document(
                id=generate_id_from_label("doc_1"),
                group_ids=[generate_id_from_label("group_1")],
                user_id=generate_id_from_label("user_id"),
                data="The quick brown fox jumps over the lazy dog.",
                type=DocumentType.TXT,
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
                        group_ids=[generate_id_from_label("group_1")],
                        user_id=generate_id_from_label("user_id"),
                        data="The quick brown fox jumps over the lazy dog.",
                        type=DocumentType.TXT,
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
                group_ids=[generate_id_from_label("group_1")],
                user_id=generate_id_from_label("user_1"),
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
        search_results["vector_search_results"][0]["text"]
        == "The quick brown fox jumps over the lazy dog."
    )

    # Delete the document
    delete_result = await app.adelete(filters={"author": {"$eq": "John Doe"}})

    # Verify the deletion was successful
    assert delete_result is None
    # Search for the document again
    search_results_2 = await app.asearch("who was aristotle?")

    # Verify that the search results are empty
    assert (
        len(search_results_2["vector_search_results"]) == 0
    ), f"Expected no search results, but got {search_results_2['vector_search_results']}"


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_user_documents(app, logging_connection):

    # user_id_0 = generate_id_from_label("user_0")
    # user_id_1 = generate_id_from_label("user_1")
    user_0 = app.register("user_0@test.com", "password")
    user_id_0 = user_0.id
    user_1 = app.register("user_1@test.com", "password")
    user_id_1 = user_1.id
    doc_id_0 = generate_id_from_label("doc_01")
    doc_id_1 = generate_id_from_label("doc_11")

    await app.aingest_documents(
        [
            Document(
                id=doc_id_0,
                group_ids=[generate_id_from_label("group_0")],
                user_id=user_id_0,
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
            Document(
                id=doc_id_1,
                group_ids=[generate_id_from_label("group_1")],
                user_id=user_id_1,
                data="The lazy dog jumps over the quick brown fox.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )
    user_stats_results = await app.ausers_overview([user_id_0, user_id_1])
    print("user_stats_results = ", user_stats_results)
    user_id_results = [stats.user_id for stats in user_stats_results]
    print("user_id_results = ", user_stats_results)
    assert set([user_id_0, user_id_1]) == set(
        user_id_results
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
        user_0_docs[0].id == doc_id_0
    ), f"Expected document id {doc_id_0} for user {user_id_0}, but got {user_0_docs[0].id}"
    assert (
        user_1_docs[0].id == doc_id_1
    ), f"Expected document id {doc_id_1} for user {user_id_1}, but got {user_1_docs[0].id}"

    # Clean up
    delete_result = await app.adelete(
        filters={"document_id": {"$in": [doc_id_0, doc_id_1]}}
    )

    assert delete_result is None


@pytest.mark.parametrize("app", ["postgres"], indirect=True)
@pytest.mark.asyncio
async def test_delete_by_id(app, logging_connection):
    doc_id = generate_id_from_label("doc_0")
    await app.aingest_documents(
        [
            Document(
                id=doc_id,
                group_ids=[],
                user_id=generate_id_from_label("user_0"),
                data="The quick brown fox jumps over the lazy dog.",
                type="txt",
                metadata={"author": "John Doe"},
            ),
        ]
    )
    search_results = await app.asearch("who was aristotle?")

    assert len(search_results["vector_search_results"]) > 0
    delete_result = await app.adelete(filters={"document_id": {"$eq": doc_id}})
    assert delete_result is None
    search_results = await app.asearch("who was aristotle?")
    assert len(search_results["vector_search_results"]) == 0
