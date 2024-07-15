from enum import Enum, auto


class EmbeddingPurpose(str, Enum):
    INDEX = auto()
    QUERY = auto()
    DOCUMENT = auto()


default_embedding_prefixes = {
    "nomic-embed-text-v1.5": {
        EmbeddingPurpose.INDEX: "",
        EmbeddingPurpose.QUERY: "search_query: ",
        EmbeddingPurpose.DOCUMENT: "search_document: ",
    },
    "nomic-embed-text": {
        EmbeddingPurpose.INDEX: "",
        EmbeddingPurpose.QUERY: "search_query: ",
        EmbeddingPurpose.DOCUMENT: "search_document: ",
    },
    "mixedbread-ai/mxbai-embed-large-v1": {
        EmbeddingPurpose.INDEX: "",
        EmbeddingPurpose.QUERY: "Represent this sentence for searching relevant passages: ",
        EmbeddingPurpose.DOCUMENT: "Represent this sentence for searching relevant passages: ",
    },
    "mixedbread-ai/mxbai-embed-large": {
        EmbeddingPurpose.INDEX: "",
        EmbeddingPurpose.QUERY: "Represent this sentence for searching relevant passages: ",
        EmbeddingPurpose.DOCUMENT: "Represent this sentence for searching relevant passages: ",
    },
}
