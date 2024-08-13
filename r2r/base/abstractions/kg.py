from typing import Optional

from pydantic import BaseModel

from r2r.base.abstractions.document import logger


class Entity(BaseModel):
    """An entity extracted from a document."""

    category: str
    subcategory: Optional[str] = None
    value: str

    def __str__(self):
        return (
            f"{self.category}:{self.subcategory}:{self.value}"
            if self.subcategory
            else f"{self.category}:{self.value}"
        )


class Triple(BaseModel):
    """A triple extracted from a document."""

    subject: str
    predicate: str
    object: str


def extract_entities(llm_payload: list[str]) -> dict[str, Entity]:
    entities = {}
    for entry in llm_payload:
        try:
            if "], " in entry:  # Check if the entry is an entity
                entry_val = entry.split("], ")[0] + "]"
                entry = entry.split("], ")[1]
                colon_count = entry.count(":")

                if colon_count == 1:
                    category, value = entry.split(":")
                    subcategory = None
                elif colon_count >= 2:
                    parts = entry.split(":", 2)
                    category, subcategory, value = (
                        parts[0],
                        parts[1],
                        parts[2],
                    )
                else:
                    raise ValueError("Unexpected entry format")

                entities[entry_val] = Entity(
                    category=category, subcategory=subcategory, value=value
                )
        except Exception as e:
            logger.error(f"Error processing entity {entry}: {e}")
            continue
    return entities


def extract_triples(
    llm_payload: list[str], entities: dict[str, Entity]
) -> list[Triple]:
    triples = []
    for entry in llm_payload:
        try:
            if "], " not in entry:  # Check if the entry is an entity
                elements = entry.split(" ")
                subject = elements[0]
                predicate = elements[1]
                object = " ".join(elements[2:])
                subject = entities[subject].value  # Use entity.value
                if "[" in object and "]" in object:
                    object = entities[object].value  # Use entity.value
                triples.append(
                    Triple(subject=subject, predicate=predicate, object=object)
                )
        except Exception as e:
            logger.error(f"Error processing triplet {entry}: {e}")
            continue
    return triples


class KGExtraction(BaseModel):
    """An extraction from a document that is part of a knowledge graph."""

    entities: dict[str, Entity]
    triples: list[Triple]
