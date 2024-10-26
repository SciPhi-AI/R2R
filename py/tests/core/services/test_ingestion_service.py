# from uuid import UUID

# import pytest

# from core.base import RawChunk
# from core.main.services.ingestion_service import IngestionService
# from core.main.abstractions import R2RProviders


# @pytest.fixture
# def r2r_providers(
#     r2r_ingestion_provider,
#     postgres_db_provider,
#     litellm_provider_128,
#     r2r_auth_provider,
#     litellm_completion_provider,
#     orchestration_provider,
#     local_logging_provider,
# ):
#     return R2RProviders(
#         ingestion=r2r_ingestion_provider,
#         database=postgres_db_provider,
#         embedding=litellm_provider_128,
#         auth=r2r_auth_provider,
#         llm=litellm_completion_provider,
#         orchestration=orchestration_provider,
#         logging=local_logging_provider
#     )


# @pytest.fixture
# async def ingestion_service(r2r_providers, ingestion_config):
#     # You'll need to mock your dependencies here
#     service = IngestionService(
#         providers=r2r_providers,
#         config=ingestion_config,
#         pipes=[],
#         pipelines=[],
#         agents=[],
#         run_manager=None,
#         logging_connection=None,
#     )
#     return service

# @pytest.fixture
# def sample_document_id():
#     return UUID("12345678-1234-5678-1234-567812345678")


# @pytest.fixture
# def sample_chunks():
#     return [
#         RawChunk(
#             text="This is the first chunk of text.",
#             metadata={"chunk_order": 1},
#         ),
#         RawChunk(
#             text="This is the second chunk with different content.",
#             metadata={"chunk_order": 2},
#         ),
#         RawChunk(
#             text="And this is the third chunk with more information.",
#             metadata={"chunk_order": 3},
#         ),
#     ]


# async def test_ingest_chunks_ingress_success(
#     ingestion_service, sample_document_id, sample_chunks
# ):
#     """Test successful ingestion of chunks"""
#     result = await ingestion_service.ingest_chunks_ingress(
#         document_id=sample_document_id,
#         chunks=sample_chunks,
#         metadata={"title": "Test Document"},
#         user="test_user",
#     )

#     assert result is not None
#     # Add assertions based on your expected return type


# async def test_ingest_chunks_ingress_empty_chunks(
#     ingestion_service, sample_document_id
# ):
#     """Test handling of empty chunks list"""
#     with pytest.raises(ValueError):
#         await ingestion_service.ingest_chunks_ingress(
#             document_id=sample_document_id,
#             chunks=[],
#             metadata={},
#             user_id="test_user",
#         )


# async def test_ingest_chunks_ingress_invalid_metadata(
#     ingestion_service, sample_document_id, sample_chunks
# ):
#     """Test handling of invalid metadata"""
#     with pytest.raises(TypeError):
#         await ingestion_service.ingest_chunks_ingress(
#             document_id=sample_document_id,
#             chunks=sample_chunks,
#             metadata=None,  # Invalid metadata
#             user_id="test_user",
#         )


# async def test_ingest_chunks_ingress_large_document(
#     ingestion_service, sample_document_id
# ):
#     """Test ingestion of a large number of chunks"""
#     large_chunks = [
#         RawChunk(text=f"Chunk number {i}", metadata={"chunk_order": i})
#         for i in range(1000)
#     ]

#     result = await ingestion_service.ingest_chunks_ingress(
#         document_id=sample_document_id,
#         chunks=large_chunks,
#         metadata={"title": "Large Document"},
#         user_id="test_user",
#     )

#     assert result is not None
#     # Add assertions for large document handling


# async def test_ingest_chunks_ingress_duplicate_chunk_orders(
#     ingestion_service, sample_document_id
# ):
#     """Test handling of chunks with duplicate chunk orders"""
#     duplicate_chunks = [
#         RawChunk(text="First chunk", metadata={"chunk_order": 1}),
#         RawChunk(
#             text="Second chunk",
#             metadata={"chunk_order": 1},  # Duplicate chunk_order
#         ),
#     ]

#     with pytest.raises(ValueError):
#         await ingestion_service.ingest_chunks_ingress(
#             document_id=sample_document_id,
#             chunks=duplicate_chunks,
#             metadata={},
#             user_id="test_user",
#         )


# async def test_ingest_chunks_ingress_invalid_user(
#     ingestion_service, sample_document_id, sample_chunks
# ):
#     """Test handling of invalid user ID"""
#     with pytest.raises(ValueError):
#         await ingestion_service.ingest_chunks_ingress(
#             document_id=sample_document_id,
#             chunks=sample_chunks,
#             metadata={},
#             user_id="",  # Invalid user ID
#         )


# async def test_ingest_chunks_ingress_metadata_validation(
#     ingestion_service, sample_document_id, sample_chunks
# ):
#     """Test metadata validation"""
#     test_cases = [
#         ({"title": "Valid title"}, True),
#         ({"title": ""}, False),
#         ({"invalid_key": "value"}, False),
#         (
#             {},
#             True,
#         ),  # Empty metadata might be valid depending on your requirements
#     ]

#     for metadata, should_succeed in test_cases:
#         if should_succeed:
#             result = await ingestion_service.ingest_chunks_ingress(
#                 document_id=sample_document_id,
#                 chunks=sample_chunks,
#                 metadata=metadata,
#                 user_id="test_user",
#             )
#             assert result is not None
#         else:
#             with pytest.raises((ValueError, TypeError)):
#                 await ingestion_service.ingest_chunks_ingress(
#                     document_id=sample_document_id,
#                     chunks=sample_chunks,
#                     metadata=metadata,
#                     user_id="test_user",
#                 )


# async def test_ingest_chunks_ingress_concurrent_requests(
#     ingestion_service, sample_chunks
# ):
#     """Test handling of concurrent ingestion requests"""
#     import asyncio

#     document_ids = [
#         UUID("12345678-1234-5678-1234-56781234567" + str(i)) for i in range(5)
#     ]

#     async def ingest_document(doc_id):
#         return await ingestion_service.ingest_chunks_ingress(
#             document_id=doc_id,
#             chunks=sample_chunks,
#             metadata={"title": f"Document {doc_id}"},
#             user_id="test_user",
#         )

#     results = await asyncio.gather(
#         *[ingest_document(doc_id) for doc_id in document_ids]
#     )

#     assert len(results) == len(document_ids)
#     for result in results:
#         assert result is not None
