from enum import Enum


class RunType(str, Enum):
    """Enumeration of the different types of runs."""

    RESTRUCTURE = "RESTRUCTURE"
    RETRIEVAL = "RETRIEVAL"
    INGESTION = "INGESTION"
    MANAGEMENT = "MANAGEMENT"
    AUTH = "AUTH"
    UNSPECIFIED = "UNSPECIFIED"
