class CollectionNotInitializedError(Exception):
    pass


class MilvusDBInitializationError(Exception):
    pass


class PymilvusImportError(Exception):
    pass


class MilvusCilentConnectionError(Exception):
    pass


class CollectionCreationError(Exception):
    pass


class CollectionDeletionError(Exception):
    pass