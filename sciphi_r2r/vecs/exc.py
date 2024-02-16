__all__ = [
    "VecsException",
    "CollectionAlreadyExists",
    "CollectionNotFound",
    "ArgError",
    "FilterError",
    "IndexNotFound",
    "Unreachable",
]


class VecsException(Exception):
    """
    Base exception class for the 'vecs' package.
    All custom exceptions in the 'vecs' package should derive from this class.
    """

    ...


class CollectionAlreadyExists(VecsException):
    """
    Exception raised when attempting to create a collection that already exists.
    """

    ...


class CollectionNotFound(VecsException):
    """
    Exception raised when attempting to access or manipulate a collection that does not exist.
    """

    ...


class ArgError(VecsException):
    """
    Exception raised for invalid arguments when calling a method.
    """

    ...


class MismatchedDimension(ArgError):
    """
    Exception raised when multiple sources of truth for a collection's embedding dimension do not match.
    """

    ...


class FilterError(VecsException):
    """
    Exception raised when there's an error related to filter usage in a query.
    """

    ...


class IndexNotFound(VecsException):
    """
    Exception raised when attempting to access an index that does not exist.
    """

    ...


class Unreachable(VecsException):
    """
    Exception raised when an unreachable part of the code is executed.
    This is typically used for error handling in cases that should be logically impossible.
    """

    ...


class MissingDependency(VecsException, ImportError):
    """
    Exception raised when attempting to access a feature that requires an optional dependency when the optional dependency is not present.
    """

    ...
