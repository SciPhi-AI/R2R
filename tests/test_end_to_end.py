import asyncio
import os
import uuid

import pytest
from fastapi.datastructures import UploadFile

from r2r import (
    Document,
    KVLoggingSingleton,
    R2RConfig,
    R2REngine,
    R2RPipeFactory,
    R2RPipelineFactory,
    R2RProviderFactory,
    VectorSearchSettings,
    generate_id_from_label,
)
from r2r.base.abstractions.llm import GenerationConfig


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
    config = R2RConfig.from_json()
    config.logging.provider = "local"
    config.logging.logging_path = uuid.uuid4().hex

    vector_db_provider = request.param
    if vector_db_provider == "pgvector":
        config.vector_database.provider = "pgvector"
        config.vector_database.extra_fields["vecs_collection"] = (
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
        )

        try:
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


@pytest.mark.parametrize("app", ["pgvector"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_txt_document(app, logging_connection):
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


@pytest.mark.parametrize("app", ["pgvector"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_txt_file(app, logging_connection):
    try:
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
    except asyncio.CancelledError:
        pass


@pytest.mark.parametrize("app", ["pgvector"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_search_txt_file(app, logging_connection):
    try:
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

        await app.aingest_files(metadatas=[metadata], files=files)

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
        run_info = await logging_connection.get_run_info(
            log_type_filter="search"
        )

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
    except asyncio.CancelledError:
        pass


@pytest.mark.parametrize("app", ["pgvector"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_search_then_delete(app, logging_connection):
    try:
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
        delete_result = await app.adelete(["author"], ["John Doe"])

        # Verify the deletion was successful
        expected_deletion_message = "deleted successfully"
        assert (
            expected_deletion_message in delete_result
        ), f"Expected successful deletion message, but got {delete_result}"

        # Search for the document again
        search_results_2 = await app.asearch("who was aristotle?")

        # Verify that the search results are empty
        assert (
            len(search_results_2["vector_search_results"]) == 0
        ), f"Expected no search results, but got {search_results_2['results']}"
    except asyncio.CancelledError:
        pass


@pytest.mark.parametrize("app", ["local", "pgvector"], indirect=True)
@pytest.mark.asyncio
async def test_ingest_user_documents(app, logging_connection):
    try:
        user_id_0 = generate_id_from_label("user_0")
        user_id_1 = generate_id_from_label("user_1")

        try:
            await app.aingest_documents(
                [
                    Document(
                        id=generate_id_from_label("doc_01"),
                        data="The quick brown fox jumps over the lazy dog.",
                        type="txt",
                        metadata={"author": "John Doe", "user_id": user_id_0},
                    ),
                    Document(
                        id=generate_id_from_label("doc_11"),
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
            assert user_0_docs[0].document_id == generate_id_from_label(
                "doc_01"
            ), f"Expected document id {str(generate_id_from_label('doc_0'))} for user {user_id_0}, but got {user_0_docs[0].document_id}"
            assert user_1_docs[0].document_id == generate_id_from_label(
                "doc_11"
            ), f"Expected document id {str(generate_id_from_label('doc_1'))} for user {user_id_1}, but got {user_1_docs[0].document_id}"
        finally:
            await app.adelete(
                ["document_id", "document_id"],
                [
                    str(generate_id_from_label("doc_01")),
                    str(generate_id_from_label("doc_11")),
                ],
            )
    except asyncio.CancelledError:
        pass


@pytest.mark.parametrize("app", ["pgvector"], indirect=True)
@pytest.mark.asyncio
async def test_delete_by_id(app, logging_connection):
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
        search_results = await app.asearch("who was aristotle?")

        assert len(search_results["vector_search_results"]) > 0
        await app.adelete(
            ["document_id"], [str(generate_id_from_label("doc_1"))]
        )
        search_results = await app.asearch("who was aristotle?")
        assert len(search_results["vector_search_results"]) == 0
    except asyncio.CancelledError:
        pass


@pytest.mark.parametrize("app", ["pgvector"], indirect=True)
@pytest.mark.asyncio
async def test_double_ingest(app, logging_connection):
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
        search_results = await app.asearch("who was aristotle?")

        assert len(search_results["vector_search_results"]) == 1
        with pytest.raises(Exception):
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
