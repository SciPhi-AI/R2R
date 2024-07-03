from r2r import R2R, Document, GenerationConfig

app = R2R()  # You may pass a custom configuration to `R2R`

app.ingest_documents(
    [
        Document(
            type="txt",
            data="John is a person that works at Google.",
            metadata={},
        )
    ]
)

rag_results = app.rag(
    "Who is john", GenerationConfig(model="gpt-3.5-turbo", temperature=0.0)
)
print(f"Search Results:\n{rag_results.search_results}")
print(f"Completion:\n{rag_results.completion}")

# RAG Results:
# Search Results:
# AggregateSearchResult(vector_search_results=[VectorSearchResult(id=2d71e689-0a0e-5491-a50b-4ecb9494c832, score=0.6848798582029441, metadata={'text': 'John is a person that works at Google.', 'version': 'v0', 'chunk_order': 0, 'document_id': 'ed76b6ee-dd80-5172-9263-919d493b439a', 'extraction_id': '1ba494d7-cb2f-5f0e-9f64-76c31da11381', 'associatedQuery': 'Who is john'})], kg_search_results=None)
# Completion:
# ChatCompletion(id='chatcmpl-9g0HnjGjyWDLADe7E2EvLWa35cMkB', choices=[Choice(finish_reason='stop', index=0, logprobs=None, message=ChatCompletionMessage(content='John is a person that works at Google [1].', role='assistant', function_call=None, tool_calls=None))], created=1719797903, model='gpt-3.5-turbo-0125', object='chat.completion', service_tier=None, system_fingerprint=None, usage=CompletionUsage(completion_tokens=11, prompt_tokens=145, total_tokens=156))
