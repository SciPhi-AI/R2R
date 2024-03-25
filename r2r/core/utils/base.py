import uuid


def generate_run_id() -> str:
    return str(uuid.uuid4())


def generate_doc_id(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, label))
