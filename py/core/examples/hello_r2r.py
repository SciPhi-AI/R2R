from r2r import R2RClient

client = R2RClient()

with open("test.txt", "w") as file:
    file.write("John is a person that works at Google.")

client.ingest_files(file_paths=["test.txt"])

# Call RAG directly on an R2R object
rag_response = client.rag(
    query="Who is john",
    rag_generation_config={"model": "gpt-4o-mini", "temperature": 0.0},
)
results = rag_response["results"]
print(f"Search Results:\n{results['search_results']}")
print(f"Completion:\n{results['completion']}")

# RAG Results:
# Search Results:
# AggregateSearchResult(chunk_search_results=[ChunkSearchResult(id=2d71e689-0a0e-5491-a50b-4ecb9494c832, score=0.6848798582029441, metadata={'text': 'John is a person that works at Google.', 'version': 'v0', 'chunk_order': 0, 'document_id': 'ed76b6ee-dd80-5172-9263-919d493b439a', 'id': '1ba494d7-cb2f-5f0e-9f64-76c31da11381', 'associatedQuery': 'Who is john'})], graph_search_results=None)
# Completion:
# ChatCompletion(id='chatcmpl-9g0HnjGjyWDLADe7E2EvLWa35cMkB', choices=[Choice(finish_reason='stop', index=0, logprobs=None, message=ChatCompletionMessage(content='John is a person that works at Google [1].', role='assistant', function_call=None, tool_calls=None))], created=1719797903, model='gpt-4o-mini', object='chat.completion', service_tier=None, system_fingerprint=None, usage=CompletionUsage(completion_tokens=11, prompt_tokens=145, total_tokens=156))
