import logging

from r2r.core import EmbeddingProvider, PipelineStage, VectorSearchResult

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        config: dict,
    ):
        super().__init__(config)
        logger.info(
            "Initializing `SentenceTransformerEmbeddingProvider` with separate models for search and rerank."
        )
        provider = config.get("provider", None)
        if not provider:
            raise ValueError(
                "Must set provider in order to initialize SentenceTransformerEmbeddingProvider."
            )
        if provider != "sentence-transformers":
            raise ValueError(
                "SentenceTransformerEmbeddingProvider must be initialized with provider `sentence-transformers`."
            )
        try:
            from sentence_transformers import CrossEncoder, SentenceTransformer

            self.SentenceTransformer = SentenceTransformer
            # TODO - Modify this to be configurable, as `bge-reranker-large` is a `SentenceTransformer` model
            self.CrossEncoder = CrossEncoder
        except ImportError:
            raise ValueError(
                "Must download sentence-transformers library to run `SentenceTransformerEmbeddingProvider`."
            )

        # Initialize separate models for search and rerank
        self.do_search = False
        self.do_rerank = False

        self.search_encoder = self._init_model(config, PipelineStage.SEARCH)
        self.rerank_encoder = self._init_model(config, PipelineStage.RERANK)

    def _init_model(self, config: dict, stage: str):
        stage_name = stage.name.lower()
        model = config.get(f"{stage_name}_model", None)
        dimension = config.get(f"{stage_name}_dimension", None)
        transformer_type = config.get(
            f"{stage_name}_transformer_type", "SentenceTransformer"
        )

        if stage == PipelineStage.SEARCH:
            self.do_search = True
            # Check if a model is set for the stage
            if not (model and dimension and transformer_type):
                raise ValueError(
                    f"Must set {stage}_model and {stage}_dimension for {stage} stage in order to initialize SentenceTransformerEmbeddingProvider."
                )

        if stage == PipelineStage.RERANK:
            # Check if a model is set for the stage
            if not (model and dimension and transformer_type):
                return None

            self.do_rerank = True
            if transformer_type == "SentenceTransformer":
                raise ValueError(
                    f"`SentenceTransformer` models are not yet supported for {stage} stage in SentenceTransformerEmbeddingProvider."
                )

        # Save the model_key and dimension into instance variables
        setattr(self, f"{stage_name}_model", model)
        setattr(self, f"{stage_name}_dimension", dimension)
        setattr(self, f"{stage_name}_transformer_type", transformer_type)

        # Initialize the model
        encoder = (
            self.SentenceTransformer(
                model, truncate_dim=dimension, trust_remote_code=True
            )
            if transformer_type == "SentenceTransformer"
            else self.CrossEncoder(model, trust_remote_code=True)
        )
        return encoder

    def get_embedding(
        self, text: str, stage: PipelineStage = PipelineStage.SEARCH
    ) -> list[float]:
        if stage != PipelineStage.SEARCH:
            raise ValueError("`get_embedding` only supports `SEARCH` stage.")
        if not self.do_search:
            raise ValueError(
                "`get_embedding` can only be called for the search stage if a search model is set."
            )
        encoder = self.search_encoder
        return encoder.encode([text]).tolist()[0]

    def get_embeddings(
        self, texts: list[str], stage: PipelineStage = PipelineStage.SEARCH
    ) -> list[list[float]]:
        if stage != PipelineStage.SEARCH:
            raise ValueError("`get_embeddings` only supports `SEARCH` stage.")
        if not self.do_search:
            raise ValueError(
                "`get_embeddings` can only be called for the search stage if a search model is set."
            )
        encoder = (
            self.search_encoder
            if stage == PipelineStage.SEARCH
            else self.rerank_encoder
        )
        return encoder.encode(texts).tolist()

    def rerank(
        self,
        query: str,
        documents: list[VectorSearchResult],
        stage: PipelineStage = PipelineStage.RERANK,
        limit: int = 10,
    ) -> list[list[float]]:
        if stage != PipelineStage.RERANK:
            raise ValueError("`rerank` only supports `RERANK` stage.")
        if not self.do_rerank:
            return documents[:limit]

        from copy import copy

        texts = copy([doc.metadata["text"] for doc in documents])
        # Use the rank method from the rerank_encoder, which is a CrossEncoder model
        reranked_scores = self.rerank_encoder.rank(
            query, texts, return_documents=False, top_k=limit
        )
        # Map the reranked scores back to the original documents
        reranked_results = []
        for score in reranked_scores:
            corpus_id = score["corpus_id"]
            new_result = documents[corpus_id]
            new_result.score = float(score["score"])
            reranked_results.append(new_result)

        # Sort the documents by the new scores in descending order
        reranked_results.sort(key=lambda doc: doc.score, reverse=True)
        import pdb

        pdb.set_trace()
        return reranked_results

    def tokenize_string(
        self, stage: PipelineStage = PipelineStage.SEARCH
    ) -> list[int]:
        raise ValueError(
            "SentenceTransformerEmbeddingProvider does not support tokenize_string."
        )
