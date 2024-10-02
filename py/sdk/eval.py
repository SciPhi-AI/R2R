from datasets import Dataset
from typing import Union
from .models import RagEvalResult

class EvalMethods:

    @staticmethod
    async def evaluate_rag(client, collection_id: str, dataset: Union[Dataset, list[dict]]) -> RagEvalResult:
        """
        Evaluate RAG performance for a given collection and dataset.
        """

        if isinstance(dataset, Dataset):
            dataset = dataset.to_dict()

        return await client._make_request(
            "POST",
            "evaluate_rag",
            data={"collection_id": collection_id, "dataset": dataset},
        )
