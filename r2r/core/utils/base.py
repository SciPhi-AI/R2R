import uuid


def generate_run_id() -> str:
    return str(uuid.uuid4())


def generate_id_from_label(label: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, label))
