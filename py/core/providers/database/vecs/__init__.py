from . import exc
from .client import Client
from .vector_collection import VectorCollection

__project__ = "vecs"
__version__ = "0.4.2"


__all__ = [
    "VectorCollection",
    "Client",
    "exc",
]


def create_client(connection_string: str, *args, **kwargs) -> Client:
    """Creates a client from a Postgres connection string"""
    return Client(connection_string, *args, **kwargs)
