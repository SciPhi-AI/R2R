from .hatchet.ingestion_workflow import hatchet_ingestion_factory
from .hatchet.kg_workflow import hatchet_kg_factory
from .simple.ingestion_workflow import simple_ingestion_factory
from .simple.kg_workflow import simple_kg_factory

__all__ = [
    "hatchet_ingestion_factory",
    "hatchet_kg_factory",
    "simple_ingestion_factory",
    "simple_kg_factory",
]
