from datasets import Dataset
from typing import Union, Optional
from uuid import UUID
from .models import RagEvalResult

class EvalMethods:

    @staticmethod
    async def evaluate_rag(client, dataset: Union[Dataset, list[dict]], collection_id: Optional[UUID] = None) -> RagEvalResult:
        """
        Evaluate RAG performance for a given collection and dataset.
        """

        # create a new prompt
        prompt = "You are a helpful assistant."

        

        if isinstance(dataset, Dataset):
            dataset = dataset.to_dict()

        for question in dataset:


        data = {"dataset": dataset}
        if collection_id is not None:
            data["collection_id"] = collection_id
