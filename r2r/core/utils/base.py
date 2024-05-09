import uuid


def generate_run_id() -> uuid.UUID:
    return uuid.uuid4()


def generate_id_from_label(label: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, label)
