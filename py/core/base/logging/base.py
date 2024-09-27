from enum import Enum


class RunType(str, Enum):
    """Enumeration of the different types of runs."""

    RETRIEVAL = "RETRIEVAL"
    MANAGEMENT = "MANAGEMENT"
    INGESTION = "INGESTION"
    AUTH = "AUTH"
    UNSPECIFIED = "UNSPECIFIED"
    KG = "KG"
