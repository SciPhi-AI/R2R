import logging
import os
from typing import Any, Optional

from r2r.core import KGConfig, KGProvider

logger = logging.getLogger(__name__)

node_properties_query = """
CALL apoc.meta.data()
YIELD label, other, elementType, type, property
WHERE NOT type = "RELATIONSHIP" AND elementType = "node"
WITH label AS nodeLabels, collect({property:property, type:type}) AS properties
RETURN {labels: nodeLabels, properties: properties} AS output
"""

rel_properties_query = """
CALL apoc.meta.data()
YIELD label, other, elementType, type, property
WHERE NOT type = "RELATIONSHIP" AND elementType = "relationship"
WITH label AS nodeLabels, collect({property:property, type:type}) AS properties
RETURN {type: nodeLabels, properties: properties} AS output
"""

rel_query = """
CALL apoc.meta.data()
YIELD label, other, elementType, type, property
WHERE type = "RELATIONSHIP" AND elementType = "node"
UNWIND other AS other_node
RETURN {start: label, type: property, end: toString(other_node)} AS output
"""


class Neo4jKGProvider(KGProvider):
    def __init__(self, config: KGConfig, **kwargs: Any) -> None:
        super().__init__(config)
        if config.provider != "neo4j":
            raise ValueError(
                "Neo4jKGProvider must be initialized with config with `neo4j` provider."
            )

        username = os.getenv("NEO4J_USER")
        password = os.getenv("NEO4J_PASSWORD")
        url = os.getenv("NEO4J_URL")
        database = os.getenv("NEO4J_DATABASE", "neo4j")

        if not username or not password or not url:
            raise ValueError(
                "Neo4j configuration values are missing. Please set NEO4J_USER, NEO4J_PASSWORD, and NEO4J_URL environment variables."
            )

        try:
            import neo4j
        except ImportError:
            raise ImportError("Please install neo4j: pip install neo4j")

        self.node_label = kwargs.get("node_label", "Entity")
        self._driver = neo4j.GraphDatabase.driver(
            url, auth=(username, password)
        )
        self._database = database
        self.schema = ""
        self.structured_schema: dict[str, Any] = {}
        # Verify connection
        try:
            self._driver.verify_connectivity()
        except neo4j.exceptions.ServiceUnavailable:
            raise ValueError(
                "Could not connect to Neo4j database. "
                "Please ensure that the URL is correct"
            )
        except neo4j.exceptions.AuthError:
            raise ValueError(
                "Could not connect to Neo4j database. "
                "Please ensure that the username and password are correct"
            )
        # Set schema
        try:
            self.refresh_schema()
        except neo4j.exceptions.ClientError:
            raise ValueError(
                "Could not use APOC procedures. "
                "Please ensure the APOC plugin is installed in Neo4j and that "
                "'apoc.meta.data()' is allowed in Neo4j configuration "
            )
        # Create constraint for faster insert and retrieval
        try:  # Using Neo4j 5
            self.query(
                """
                CREATE CONSTRAINT IF NOT EXISTS FOR (n:%s) REQUIRE n.id IS UNIQUE;
                """
                % (self.node_label)
            )
        except Exception:  # Using Neo4j <5
            self.query(
                """
                CREATE CONSTRAINT IF NOT EXISTS ON (n:%s) ASSERT n.id IS UNIQUE;
                """
                % (self.node_label)
            )

    @property
    def client(self) -> Any:
        return self._driver

    def get(self, subj: str) -> list[list[str]]:
        """Get triplets."""
        query = """
            MATCH (n1:%s)-[r]->(n2:%s)
            WHERE n1.id = $subj
            RETURN type(r), n2.id;
        """
        prepared_statement = query % (self.node_label, self.node_label)
        with self._driver.session(database=self._database) as session:
            data = session.run(prepared_statement, {"subj": subj})
            return [record.values() for record in data]

    def get_rel_map(
        self,
        subjs: Optional[list[str]] = None,
        depth: int = 2,
        limit: int = 30,
    ) -> dict[str, list[list[str]]]:
        """Get flat rel map."""
        rel_map: dict[Any, list[Any]] = {}
        if subjs is None or len(subjs) == 0:
            return rel_map
        query = (
            f"""MATCH p=(n1:{self.node_label})-[*1..{depth}]->() """
            f"""{"WHERE n1.id IN $subjs" if subjs else ""} """
            "UNWIND relationships(p) AS rel "
            "WITH n1.id AS subj, p, apoc.coll.flatten(apoc.coll.toSet("
            "collect([type(rel), endNode(rel).id]))) AS flattened_rels "
            f"RETURN subj, collect(flattened_rels) AS flattened_rels LIMIT {limit}"
        )
        data = list(self.query(query, {"subjs": subjs}))
        if not data:
            return rel_map
        for record in data:
            rel_map[record["subj"]] = record["flattened_rels"]
        return rel_map

    def upsert_triplet(self, subj: str, rel: str, obj: str) -> None:
        """Add triplet."""
        query = """
            MERGE (n1:`%s` {id:$subj})
            MERGE (n2:`%s` {id:$obj})
            MERGE (n1)-[:`%s`]->(n2)
        """
        prepared_statement = query % (
            self.node_label,
            self.node_label,
            rel.replace(" ", "_").upper(),
        )
        with self._driver.session(database=self._database) as session:
            session.run(prepared_statement, {"subj": subj, "obj": obj})

    def delete(self, subj: str, rel: str, obj: str) -> None:
        """Delete triplet."""

        def delete_rel(subj: str, obj: str, rel: str) -> None:
            with self._driver.session(database=self._database) as session:
                session.run(
                    (
                        "MATCH (n1:{})-[r:{}]->(n2:{}) WHERE n1.id = $subj AND n2.id"
                        " = $obj DELETE r"
                    ).format(self.node_label, rel, self.node_label),
                    {"subj": subj, "obj": obj},
                )

        def delete_entity(entity: str) -> None:
            with self._driver.session(database=self._database) as session:
                session.run(
                    "MATCH (n:%s) WHERE n.id = $entity DELETE n"
                    % self.node_label,
                    {"entity": entity},
                )

        def check_edges(entity: str) -> bool:
            with self._driver.session(database=self._database) as session:
                is_exists_result = session.run(
                    "MATCH (n1:%s)--() WHERE n1.id = $entity RETURN count(*)"
                    % (self.node_label),
                    {"entity": entity},
                )
                return bool(list(is_exists_result))

        delete_rel(subj, obj, rel)
        if not check_edges(subj):
            delete_entity(subj)
        if not check_edges(obj):
            delete_entity(obj)

    def refresh_schema(self) -> None:
        """
        Refreshes the Neo4j graph schema information.
        """
        node_properties = [
            el["output"] for el in self.query(node_properties_query)
        ]
        rel_properties = [
            el["output"] for el in self.query(rel_properties_query)
        ]
        relationships = [el["output"] for el in self.query(rel_query)]

        self.structured_schema = {
            "node_props": {
                el["labels"]: el["properties"] for el in node_properties
            },
            "rel_props": {
                el["type"]: el["properties"] for el in rel_properties
            },
            "relationships": relationships,
        }
        # Format node properties
        formatted_node_props = []
        for el in node_properties:
            props_str = ", ".join(
                [
                    f"{prop['property']}: {prop['type']}"
                    for prop in el["properties"]
                ]
            )
            formatted_node_props.append(f"{el['labels']} {{{props_str}}}")
        # Format relationship properties
        formatted_rel_props = []
        for el in rel_properties:
            props_str = ", ".join(
                [
                    f"{prop['property']}: {prop['type']}"
                    for prop in el["properties"]
                ]
            )
            formatted_rel_props.append(f"{el['type']} {{{props_str}}}")
        # Format relationships
        formatted_rels = [
            f"(:{el['start']})-[:{el['type']}]->(:{el['end']})"
            for el in relationships
        ]
        self.schema = "\n".join(
            [
                "Node properties are the following:",
                ",".join(formatted_node_props),
                "Relationship properties are the following:",
                ",".join(formatted_rel_props),
                "The relationships are the following:",
                ",".join(formatted_rels),
            ]
        )

    def get_schema(self, refresh: bool = False) -> str:
        """Get the schema of the Neo4jGraph store."""
        if self.schema and not refresh:
            return self.schema
        self.refresh_schema()
        logger.debug(f"get_schema() schema:\n{self.schema}")
        return self.schema

    def query(
        self, query: str, param_map: Optional[dict[str, Any]] = {}
    ) -> Any:
        with self._driver.session(database=self._database) as session:
            result = session.run(query, param_map)
            return [d.data() for d in result]
