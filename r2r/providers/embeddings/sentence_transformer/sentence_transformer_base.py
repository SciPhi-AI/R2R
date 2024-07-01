import logging

from r2r.base import EmbeddingConfig, EmbeddingProvider, VectorSearchResult

logger = logging.getLogger(__name__)


class SentenceTransformerEmbeddingProvider(EmbeddingProvider):
    def __init__(
        self,
        config: EmbeddingConfig,
    ):
        super().__init__(config)
        logger.info(
            "Initializing `SentenceTransformerEmbeddingProvider` with separate models for search and rerank."
        )
        provider = config.provider
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
        except ImportError as e:
            raise ValueError(
                "Must download sentence-transformers library to run `SentenceTransformerEmbeddingProvider`."
            ) from e

        # Initialize separate models for search and rerank
        self.do_search = False
        self.do_rerank = False

        self.search_encoder = self._init_model(
            config, EmbeddingProvider.PipeStage.BASE
        )
        self.rerank_encoder = self._init_model(
            config, EmbeddingProvider.PipeStage.RERANK
        )

    def _init_model(self, config: EmbeddingConfig, stage: str):
        stage_name = stage.name.lower()
        model = config.dict().get(f"{stage_name}_model", None)
        dimension = config.dict().get(f"{stage_name}_dimension", None)

        transformer_type = config.dict().get(
            f"{stage_name}_transformer_type", "SentenceTransformer"
        )

        if stage == EmbeddingProvider.PipeStage.BASE:
            self.do_search = True
            # Check if a model is set for the stage
            if not (model and dimension and transformer_type):
                raise ValueError(
                    f"Must set {stage.name.lower()}_model and {stage.name.lower()}_dimension for {stage} stage in order to initialize SentenceTransformerEmbeddingProvider."
                )

        if stage == EmbeddingProvider.PipeStage.RERANK:
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
        self,
        text: str,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[float]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError("`get_embedding` only supports `SEARCH` stage.")
        if not self.do_search:
            raise ValueError(
                "`get_embedding` can only be called for the search stage if a search model is set."
            )
        encoder = self.search_encoder
        return encoder.encode([text]).tolist()[0]

    def get_embeddings(
        self,
        texts: list[str],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[list[float]]:
        if stage != EmbeddingProvider.PipeStage.BASE:
            raise ValueError("`get_embeddings` only supports `SEARCH` stage.")
        if not self.do_search:
            raise ValueError(
                "`get_embeddings` can only be called for the search stage if a search model is set."
            )
        encoder = (
            self.search_encoder
            if stage == EmbeddingProvider.PipeStage.BASE
            else self.rerank_encoder
        )
        return encoder.encode(texts).tolist()

    def rerank(
        self,
        query: str,
        results: list[VectorSearchResult],
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.RERANK,
        limit: int = 10,
    ) -> list[VectorSearchResult]:
        if stage != EmbeddingProvider.PipeStage.RERANK:
            raise ValueError("`rerank` only supports `RERANK` stage.")
        if not self.do_rerank:
            return results[:limit]

        from copy import copy

        texts = copy([doc.metadata["text"] for doc in results])
        # Use the rank method from the rerank_encoder, which is a CrossEncoder model
        reranked_scores = self.rerank_encoder.rank(
            query, texts, return_documents=False, top_k=limit
        )
        # Map the reranked scores back to the original documents
        reranked_results = []
        for score in reranked_scores:
            corpus_id = score["corpus_id"]
            new_result = results[corpus_id]
            new_result.score = float(score["score"])
            reranked_results.append(new_result)

        # Sort the documents by the new scores in descending order
        reranked_results.sort(key=lambda doc: doc.score, reverse=True)
        return reranked_results

    def tokenize_string(
        self,
        stage: EmbeddingProvider.PipeStage = EmbeddingProvider.PipeStage.BASE,
    ) -> list[int]:
        raise ValueError(
            "SentenceTransformerEmbeddingProvider does not support tokenize_string."
        )
