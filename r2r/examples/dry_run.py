import os
from r2r import (  
    R2RPipelineFactory,
    R2RConfig,
    R2RProviderFactory,
    run_pipeline,
    R2RApp
)
# from dotenv import load_dotenv

if __name__ == "__main__":
    # load_dotenv(dotenv_path="../.env")  # Load environment variables from ".env" file
    # file_path = os.path.join(os.path.dirname(__file__))
    # print("File path = ", file_path)
    # env_file = ".env"
    # dotenv_path = os.path.join(file_path, "..", env_file)
    # dotenv_path = "/Users/ocolegrove/SciPhi/R2R-dev-2/.env"
    # print(f"Loading environment variables from {dotenv_path} ...")
    # if load_dotenv(dotenv_path=dotenv_path):
    #     print(f"Successfully loaded environment variables from {dotenv_path}")
    # else:
    #     print(f"Failed to load environment variables from {dotenv_path}")

    config = R2RConfig.from_json()

    providers = R2RProviderFactory(config) \
                    .create_providers()
    
    pipelines = R2RPipelineFactory(config, providers)  \
                    .create_pipelines()

    r2r = R2RApp(config, providers, pipelines)

    
    # query = "Who is the president of the United States?"
    # context = "The president of the United States is Joe Biden."

# if __name__ == "__main__":
#     config = R2RConfig.from_json()
#     providers = R2RProviderFactory(config).create_providers()
#     pipelines = R2RPipelineFactory(config, providers).create_pipelines()
#     # eval = LocalEvalProvider(EvalConfig(provider="local"), providers.llm, providers.prompt)
#     # print('in dry run....')
#     query = "Who is the president of the United States?"
#     context = "The president of the United States is Joe Biden."

#     query = "What is rag?"
#     context = """
# Generative AI technologies are powerful, but they're limited by what they know. While an LLM like ChatGPT can perform many tasks, every LLM's baseline knowledge has gaps based on its training data. If you ask an LLM to write something about a recent trend or event, the LLM won't have any idea what you're talking about, and the responses will be mixed at best and problematic at worst.

# LLMs' knowledge-based problems come down to two key issues:

# LLM training data tends to be hopelessly out-of-date (as of writing, ChatGPT's knowledge of the world ends at January 2022, excluding functionality like Browse with Bing and GPT-4V that provide additional context).
# LLMs extrapolate when facts aren’t available, so they confidently make false but plausible-sounding statements when there's a gap in their knowledge (called hallucination).
# Retrieval augmented generation (RAG) is a strategy that helps address both of these issues, pairing information retrieval with a set of carefully designed system prompts to anchor LLMs on precise, up-to-date, and pertinent information retrieved from an external knowledge store. Prompting LLMs with this contextual knowledge makes it possible to create domain-specific applications that require a deep and evolving understanding of facts, despite LLM training data remaining static.

# You could ask an LLM, "What is RAG?", and you might get very different responses depending on whether or not the LLM itself uses RAG:
# """
#     answer = "RAG stands for Retrieval Augmented Generation, which is a strategy that helps LLMs overcome knowledge gaps by pairing information retrieval with system prompts. It addresses issues related to outdated training data and hallucinations."
#     input = DefaultEvalPipe.EvalPayload(query=query, context=context, completion=answer)
    
#     # def run_pipeline(pipeline, input, *args, **kwargs):
#     #     if not isinstance(input, AsyncGenerator):
#     #         input = list_to_generator(input)
#     #     async def _run_pipeline(input, *args, **kwargs):
#     #         return await pipeline.run(input, *args, **kwargs)

#     #     return asyncio.run(_run_pipeline(input, *args, **kwargs))
    
#     result = run_pipeline(pipelines.eval_pipeline, input)
#     print('final result = ', result)
#     # result = 
#     # result = eval._evaluate(query, context, answer)
#     # print('result = ', result)

# #     # with open("/Users/ocolegrove/Downloads/demo3.mp4", "rb") as f:
# #     # parser = MovieParser()

# #     # async def parse_image():
# #     #     with open("/Users/ocolegrove/Downloads/demo.png", "rb") as f:
# #     #         content = f.read()
# #     #     parser = ImageParser()
# #     #     async for extraction in parser.ingest(content):
# #     #         print(extraction)

# #     # asyncio.run(parse_image())


# #     async def parse_audio():
# #         with open("/Users/ocolegrove/Downloads/qq.mp3", "rb") as f:
# #             content = f.read()
# #         parser = AudioParser()
# #         async for extraction in parser.ingest(content):
# #             print(extraction)

# #     asyncio.run(parse_audio())


# #     # async def parse_movie():
# #     #     with open("/Users/ocolegrove/Downloads/demo3.mp4", "rb") as f:
# #     #         content = f.read()
# #     #     parser = MovieParser()
# #     #     async for extraction in parser.ingest(content):
# #     #         print(extraction)

# #     # asyncio.run(parse_movie())


# # # import asyncio
# # # import json
# # # import uuid

# # # from fastapi.datastructures import UploadFile

# # # from r2r import (
# # #     R2RPipelineFactory,
# # #     Document,
# # #     PipeLoggingConnectionSingleton,
# # #     R2RApp,
# # #     R2RConfig,
# # #     R2RProviderFactory,
# # #     generate_id_from_label,
# # # )

# # # if __name__ == "__main__":
# # #     config = R2RConfig.from_json()
# # #     print("config.logging = ", config.logging)
# # #     PipeLoggingConnectionSingleton.configure(config.logging)
# # #     logging_connection = PipeLoggingConnectionSingleton()

# # #     providers = R2RProviderFactory(config).create_providers()
# # #     pipelines = R2RPipelineFactory(config, providers).create_pipelines()

# # #     r2r = R2RApp(
# # #         config=config,
# # #         providers=providers,
# # #         ingestion_pipeline=pipelines.ingestion_pipeline,
# # #         search_pipeline=pipelines.search_pipeline,
# # #         rag_pipeline=pipelines.rag_pipeline,
# # #         streaming_rag_pipeline=pipelines.streaming_rag_pipeline,
# # #     )

# # #     # async def ingest_document():
# # #     #     await r2r.ingest_documents(
# # #     #         [
# # #     #             Document(
# # #     #                 id=generate_id_from_label("doc_1"),
# # #     #                 data="The quick brown fox jumps over the lazy dog.",
# # #     #                 type="txt",
# # #     #                 metadata={"author": "John Doe"},
# # #     #             ),
# # #     #             Document(
# # #     #                 id=generate_id_from_label("doc_2"),
# # #     #                 data=open("r2r/examples/data/uber_2021.pdf", "rb").read(),
# # #     #                 type="pdf",
# # #     #                 metadata={"author": "John Doe"},
# # #     #             ),
# # #     #         ]
# # #     #     )
# # #     #     run_ids = await logging_connection.get_run_ids(
# # #     #         pipeline_type="ingestion"
# # #     #     )
# # #     #     print("ingestion_log run ids = ", run_ids)
# # #     #     ingestion_logs = await logging_connection.get_logs(run_ids)
# # #     #     print(ingestion_logs)
# # #     #     print(len(ingestion_logs))

# # #     # asyncio.run(ingest_document())

# # #     async def streaming_rag(query: str):
# # #         # async for chunk in await r2r.rag(query=query, streaming=True):
# # #         #     print(chunk)
# # #         response = await r2r.rag(message=query, streaming=True)
# # #         collector = ""
# # #         async for chunk in response.body_iterator:
# # #             collector += chunk
# # #             print("-" * 100)
# # #             print(collector)  # .decode())  # Handle the streamed chunk


# # #         ingestion_logs = await r2r.get_logs(pipeline_type="ingestion")
# # #         print("ingestion_logs = ", ingestion_logs)
# # #         print("len(ingestion_logs) = ", len(ingestion_logs["results"]))


# # #         rag_logs = await r2r.get_logs(pipeline_type="rag")
# # #         print("rag_logs = ", rag_logs)
# # #         print("len(rag_logs) = ", len(rag_logs["results"]))


# # #     asyncio.run(streaming_rag("Who was aristotle??"))

# # #     # async def get_logs():
# # #     #     run_ids = await logging_connection.get_run_ids(
# # #     #         pipeline_type="ingestion"
# # #     #     )
# # #     #     logs = await logging_connection.get_logs(run_ids)
# # #     #     print(logs)

# # #     # asyncio.run(get_logs())

# # #     # async def ingest_files():
# # #     #     # Prepare the test data
# # #     #     metadata = {"author": "John Doe"}
# # #     #     ids = [str(uuid.uuid4())]
# # #     #     files = [
# # #     #         UploadFile(
# # #     #             filename="test2.txt",
# # #     #             file=open("r2r/examples/data/test2.txt", "rb"),
# # #     #         ),
# # #     #     ]
# # #     #     # Set file size manually
# # #     #     for file in files:
# # #     #         file.file.seek(0, 2)  # Move to the end of the file
# # #     #         file.size = file.file.tell()  # Get the file size
# # #     #         file.file.seek(0)  # Move back to the start of the file

# # #     #     # Convert metadata to JSON string
# # #     #     ids_str = json.dumps(ids)
# # #     #     metadata_str = json.dumps(metadata)

# # #     #     await r2r.ingest_files(metadata=metadata_str, ids=ids_str, files=files)

# # #     #     run_ids = await logging_connection.get_run_ids(
# # #     #         pipeline_type="ingestion"
# # #     #     )
# # #     #     logs = await logging_connection.get_logs(run_ids, 100)
# # #     #     print(logs)
# # #     #     print(len(logs))

# # #     # asyncio.run(ingest_files())

# # #     # async def search(query: str):
# # #     #     results = await r2r.search(query=query, search_limit=10)
# # #     #     results = await r2r.search(query=query, search_limit=20)
# # #     #     print("results = ", results["results"])
# # #     #     print("len(results) = ", len(results["results"]))
# # #     #     assert (
# # #     #         "was an Ancient Greek philosopher and polymath"
# # #     #         in results["results"][0].metadata["text"]
# # #     #     )

# # #     # asyncio.run(search("Who was aristotle?"))

# # #     # async def rag(query: str):
# # #     #     results = await r2r.rag(query=query)
# # #     #     print(results)

# # #     # asyncio.run(rag("What was lyfts profit in 2021?"))


# # #     # async def ingest_search_then_delete():
# # #     #     await r2r.ingest_documents(
# # #     #         [
# # #     #             Document(
# # #     #                 id=generate_id_from_label("doc_1"),
# # #     #                 data="The quick brown fox jumps over the lazy dog.",
# # #     #                 type="txt",
# # #     #                 metadata={"author": "John Doe"},
# # #     #             ),
# # #     #             # Document(
# # #     #             #     id=generate_id_from_label("doc_2"),
# # #     #             #     data=open("r2r/examples/data/uber_2021.pdf", "rb").read(),
# # #     #             #     type="pdf",
# # #     #             #     metadata={"author": "John Doe"},
# # #     #             # ),
# # #     #         ]
# # #     #     )
# # #     #     search_results = await r2r.search("who was aristotle?")
# # #     #     print("search_results = ", search_results)
# # #     #     # delete_result = await r2r.delete(
# # #     #     #     "document_id", str(generate_id_from_label("doc_1"))
# # #     #     # )
# # #     #     delete_result = await r2r.delete(
# # #     #         "author", "John Doe"
# # #     #     )
# # #     #     print("delete_result = ", delete_result)
# # #     #     search_results_2 = await r2r.search("who was aristotle?")
# # #     #     print("search_results_2 = ", search_results_2)

# # #     # asyncio.run(ingest_search_then_delete())

# # #     # async def ingest_search_then_delete():
# # #     #     user_id_0 = generate_id_from_label("user_0")
# # #     #     user_id_1 = generate_id_from_label("user_1")
# # #     #     await r2r.ingest_documents(
# # #     #         [
# # #     #             Document(
# # #     #                 id=generate_id_from_label("doc_1"),
# # #     #                 data="The quick brown fox jumps over the lazy dog.",
# # #     #                 type="txt",
# # #     #                 metadata={"author": "John Doe", "user_id": user_id_0},
# # #     #             ),
# # #     #             Document(
# # #     #                 id=generate_id_from_label("doc_2"),
# # #     #                 data="The lazy dog jumps over the quick brown fox.",
# # #     #                 type="txt",
# # #     #                 metadata={"author": "John Doe", "user_id": user_id_1},
# # #     #             ),
# # #     #         ]
# # #     #     )
# # #     #     user_ids = await r2r.get_user_ids()
# # #     #     print("user_ids = ", user_ids)

# # #     #     user_0_docs = await r2r.get_user_document_ids(user_id=str(user_id_0))
# # #     #     print("user_0_docs = ", user_0_docs)
# # #     #     print(user_0_docs)
# # #     #     print(generate_id_from_label("doc_1"))
# # #     #     # print("search_results = ", search_results)
# # #     #     # # delete_result = await r2r.delete(
# # #     #     # #     "document_id", str(generate_id_from_label("doc_1"))
# # #     #     # # )
# # #     #     # delete_result = await r2r.delete(
# # #     #     #     "author", "John Doe"
# # #     #     # )
# # #     #     # print("delete_result = ", delete_result)
# # #     #     # search_results_2 = await r2r.search("who was aristotle?")
# # #     #     # print("search_results_2 = ", search_results_2)

# # #     # asyncio.run(ingest_search_then_delete())

# # #     # async def get_logs():
# # #     #     # await r2r.ingest_documents(
# # #     #     #     [
# # #     #     #         Document(
# # #     #     #             id=generate_id_from_label("doc_1"),
# # #     #     #             data="The quick brown fox jumps over the lazy dog.",
# # #     #     #             type="txt",
# # #     #     #             metadata={"author": "John Doe"},
# # #     #     #         ),
# # #     #     #     ]
# # #     #     # )
# # #     #     # run_ids = await logging_connection.get_run_ids()
# # #     #     # print("run_ids = ", run_ids)
# # #     #     results = await r2r.rag(query="what does the fox do?", search_limit=10)
# # #     #     print("results = ", results)

# # #     #     logs = await r2r.get_logs(pipeline_type="rag")
# # #     #     print("logs = ", logs)
# # #     #     print("len(logs) = ", len(logs["results"]))

# # #     # asyncio.run(get_logs())
