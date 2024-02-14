from dotenv import load_dotenv
from hatchet_sdk import Context, Hatchet

from sciphi_r2r.main.app import TextEntryModel
from sciphi_r2r.pipelines import BasicEmbeddingPipeline

load_dotenv()


def get_worker(
    hatchet: Hatchet,
    embedding_pipeline: BasicEmbeddingPipeline,
) -> Hatchet:
    @hatchet.workflow(on_events=["embedding"], name="embedding-workflow")
    class EmbeddingWorkflow:
        def __init__(self, embd_pipeline):
            self.embd_pipeline = embd_pipeline

        @hatchet.step()
        def run(self, context: Context):
            input = context.workflow_input()
            if input.get("batch") is None:
                text_entry = TextEntryModel(
                    id=input.get("id"),
                    text=input.get("text"),
                    metadata=input.get("metadata"),
                )

                result = self.embd_pipeline.run(
                    text_entry, **input.get("settings")
                )
            else:
                text_entries = [
                    TextEntryModel(
                        id=item.get("id"),
                        text=item.get("text"),
                        metadata=item.get("metadata"),
                    )
                    for item in input.get("batch")
                ]

                result = self.embd_pipeline.run(
                    text_entries, **input.get("settings")
                )

            return result

    embedding_workflow = EmbeddingWorkflow(embedding_pipeline)
    worker = hatchet.worker("sciphi-worker", max_threads=4)

    worker.register_workflow(embedding_workflow)

    return worker
