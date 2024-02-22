import uuid

import dotenv

from r2r.codesearch import Indexer
from r2r.client import SciPhiR2RClient

from r2r.main import load_config
from r2r.llms import OpenAIConfig, OpenAILLM
from r2r.core import GenerationConfig

# Initialize the client with the base URL of your API
base_url = "http://localhost:8000"  # Change this to your actual API base URL
client = SciPhiR2RClient(base_url)
dotenv.load_dotenv()

if __name__ == "__main__":
    (
        api_config,
        logging_config,
        embedding_config,
        database_config,
        language_model_config,
        text_splitter_config,
    ) = load_config()


    llm = OpenAILLM(OpenAIConfig())
    generation_config = GenerationConfig(
        model_name=language_model_config["model_name"],
        temperature=language_model_config["temperature"],
        top_p=language_model_config["top_p"],
        top_k=language_model_config["top_k"],
        max_tokens_to_sample=language_model_config["max_tokens_to_sample"],
        do_stream=language_model_config["do_stream"],
    )

    prompt = "Summarize the following code snippet in two to three sentences: \n\n{blob}"

    for i, (symbol, extraction) in enumerate(Indexer().extractor()):
        document_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, symbol))
        document_text = f"Symbol: {symbol}\nExtraction:\n\n{extraction}"
        summary = llm.get_chat_completion(
            [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt.format(blob=document_text)},
             
             ],
            generation_config
        )
        description = summary.choices[0].message.content

        entry_response = client.upsert_entries(
            [
                {
                    "document_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, symbol+"-summary-only")),
                    "blobs": {"txt": description},
                    "metadata": {"symbol": symbol, 'type': 'summary-only'},
                },
                {
                    "document_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, symbol+"-raw-only")),
                    "blobs": {"txt": document_text},
                    "metadata": {"symbol": symbol, 'type': 'raw-only'},
                },
                {
                    "document_id": str(uuid.uuid5(uuid.NAMESPACE_DNS, symbol+"-summary-plus-raw")),
                    "blobs": {"txt": f"Description:\n{description}\n{document_text}"},
                    "metadata": {"symbol": symbol, 'type': 'raw-plus-summary'},
                }
            ],
            {"embedding_settings": {"do_chunking": "false"}}
        )


        print("Upserted entry:", entry_response)
        break

    # print("Searching remote db...")
    # search_response = client.search("How do i perform logging?", 20)
    # for response in search_response:
    #     print(response['metadata']['text'])
    # # print(f"Search response:\n{search_response}\n\n")

