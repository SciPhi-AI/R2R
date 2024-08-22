# Memgraph abstraction of a Knowledge Graph provider
import json
import os
from typing import Any, Dict, List, Optional, Tuple

from r2r.base import (
    EntityType,
    KGConfig,
    KGProvider,
    PromptProvider,
    format_entity_types,
    format_relations,
)
from r2r.base.abstractions.llama_abstractions import (
    LIST_LIMIT,
    ChunkNode,
    EntityNode,
    LabelledNode,
    PropertyGraphStore,
    Relation,
    Triplet,
    VectorStoreQuery,
    clean_string_values,
    value_sanitize,
)


def remove_empty_values(input_dict):
    """
    Remove entries with empty values from the dictionary.

    Parameters:
    input_dict (dict): The dictionary from which empty values need to be removed.

    Returns:
    dict: A new dictionary with all empty values removed.
    """
    # Create a new dictionary excluding empty values
    return {key: value for key, value in input_dict.items() if value}

EXHAUSTIVE_SEARCH_LIMIT = 10000
# Threshold for returning all available prop values in graph schema
DISTINCT_VALUE_LIMIT = 10

# TODO(@DavIvek): Figure out alternative to APOC
node_properties_query = """
CALL schema.node_type_properties()
YIELD nodeType, nodeLabels, mandatory, propertyName, propertyTypes
WITH nodeLabels, collect({property: propertyName, type: propertyTypes}) AS properties
RETURN {labels: nodeLabels, properties: properties} AS output;
"""
# TODO(@DavIvek): Figure out alternative to APOC
rel_properties_query = """
CALL apoc.meta.data()
YIELD label, other, elementType, type, property
WHERE NOT type = "RELATIONSHIP" AND elementType = "relationship"
      AND NOT label in $EXCLUDED_LABELS
WITH label AS nodeLabels, collect({property:property, type:type}) AS properties
RETURN {type: nodeLabels, properties: properties} AS output
"""
# TODO(@DavIvek): Figure out alternative to APOC
rel_query = """
CALL apoc.meta.data()
YIELD label, other, elementType, type, property
WHERE type = "RELATIONSHIP" AND elementType = "node"
UNWIND other AS other_node
WITH * WHERE NOT label IN $EXCLUDED_LABELS
    AND NOT other_node IN $EXCLUDED_LABELS
RETURN {start: label, type: property, end: toString(other_node)} AS output
"""


# TODO(@antejavor): Implement the Neo4jKGProvider
class Neo4jKGProvider(PropertyGraphStore, KGProvider):
    r"""
    Neo4j Property Graph Store.

    This class implements a Neo4j property graph store.

    If you are using local Neo4j instead of aura, here's a helpful
    command for launching the docker container:

    ```bash
    docker run \
        -p 7474:7474 -p 7687:7687 \
        -v $PWD/data:/data -v $PWD/plugins:/plugins \
        --name neo4j-apoc \
        -e NEO4J_apoc_export_file_enabled=true \
        -e NEO4J_apoc_import_file_enabled=true \
        -e NEO4J_apoc_import_file_use__neo4j__config=true \
        -e NEO4JLABS_PLUGINS=\\[\"apoc\"\\] \
        neo4j:latest
    ```

    Args:
        username (str): The username for the Neo4j database.
        password (str): The password for the Neo4j database.
        url (str): The URL for the Neo4j database.
        database (Optional[str]): The name of the database to connect to. Defaults to "neo4j".

    Examples:
        `pip install llama-index-graph-stores-neo4j`

        ```python
        from llama_index.core.indices.property_graph import PropertyGraphIndex
        from llama_index.graph_stores.neo4j import Neo4jKGProvider

        # Create a Neo4jKGProvider instance
        graph_store = Neo4jKGProvider(
            username="neo4j",
            password="neo4j",
            url="bolt://localhost:7687",
            database="neo4j"
        )

        # create the index
        index = PropertyGraphIndex.from_documents(
            documents,
            property_graph_store=graph_store,
        )
        ```
    """

    supports_structured_queries: bool = True
    supports_vector_queries: bool = True

    def __init__(
        self,
        config: KGConfig,
        refresh_schema: bool = True,
        sanitize_query_output: bool = True,
        enhanced_schema: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        if config.provider != "neo4j":
            raise ValueError(
                "Neo4jKGProvider must be initialized with config with `neo4j` provider."
            )

        try:
            import neo4j
        except ImportError:
            raise ImportError("Please install neo4j: pip install neo4j")

        username = config.extra_fields.get("user", None) or os.getenv(
            "NEO4J_USER"
        )
        password = config.extra_fields.get("password", None) or os.getenv(
            "NEO4J_PASSWORD"
        )
        url = config.extra_fields.get("url", None) or os.getenv("NEO4J_URL")
        database = config.extra_fields.get("database", None) or os.getenv(
            "NEO4J_DATABASE", "neo4j"
        )

        if not username or not password or not url:
            raise ValueError(
                "Neo4j configuration values are missing. Please set NEO4J_USER, NEO4J_PASSWORD, and NEO4J_URL environment variables."
            )

        self.sanitize_query_output = sanitize_query_output
        self.enhcnaced_schema = enhanced_schema
        self._driver = neo4j.GraphDatabase.driver(
            url, auth=(username, password), **kwargs
        )
        self._async_driver = neo4j.AsyncGraphDatabase.driver(
            url,
            auth=(username, password),
            **kwargs,
        )
        self._database = database
        self.structured_schema = {}
        if refresh_schema:
            self.refresh_schema()
        self.neo4j = neo4j
        self.config = config

    @property
    def client(self):
        return self._driver

    # TODO(@DavIvek): Implement schema
    def refresh_schema(self) -> None:
        """Refresh the schema."""
        node_query_results = self.structured_query(
            node_properties_query,
        )
        node_properties = (
            [el["output"] for el in node_query_results]
            if node_query_results
            else []
        )

        rels_query_result = self.structured_query(
            rel_properties_query, 
        )
        rel_properties = (
            [el["output"] for el in rels_query_result]
            if rels_query_result
            else []
        )

        rel_objs_query_result = self.structured_query(
            rel_query,
        )
        relationships = (
            [el["output"] for el in rel_objs_query_result]
            if rel_objs_query_result
            else []
        )

        # Get constraints & indexes
        try:
            constraint = self.structured_query("SHOW CONSTRAINT INFO")
            index = self.structured_query("SHOW INDEX INFO")
        except (
            self.neo4j.exceptions.ClientError
        ):  # Read-only user might not have access to schema information
            constraint = []
            index = []

        self.structured_schema = {"node_props": {}, "rel_props": {}, "relationships": {}, "metadata": {}}
        
        # memgraph sends labels as a list, if we have multiple labels on a node we need to iterate over them 
        for el in node_properties:
            for label in el["labels"]:
                self.structured_schema["node_props"][label] = el["properties"]
        
        self.structured_schema = {
            "node_props": {
                el["labels"]: el["properties"] for el in node_properties
            },
            "rel_props": {
                el["type"]: el["properties"] for el in rel_properties
            },
            "relationships": relationships,
            "metadata": {"constraint": constraint, "index": index},
        }
        schema_counts = self.structured_query(
            "CALL apoc.meta.graphSample() YIELD nodes, relationships "
            "RETURN nodes, [rel in relationships | {name:apoc.any.property"
            "(rel, 'type'), count: apoc.any.property(rel, 'count')}]"
            " AS relationships"
        )
        # Update node info
        for node in schema_counts[0].get("nodes", []):
            node_props = self.structured_schema["node_props"].get(node["name"])
            if not node_props:  # The node has no properties
                continue
            enhanced_cypher = self._enhanced_schema_cypher(
                node["name"],
                node_props,
                node["count"] < EXHAUSTIVE_SEARCH_LIMIT,
            )
            enhanced_info = self.structured_query(enhanced_cypher)[0]["output"]
            for prop in node_props:
                if prop["property"] in enhanced_info:
                    prop.update(enhanced_info[prop["property"]])
        # Update rel info
        for rel in schema_counts[0].get("relationships", []):
            rel_props = self.structured_schema["rel_props"].get(rel["name"])
            if not rel_props:  # The rel has no properties
                continue
            enhanced_cypher = self._enhanced_schema_cypher(
                rel["name"],
                rel_props,
                rel["count"] < EXHAUSTIVE_SEARCH_LIMIT,
                is_relationship=True,
            )
            try:
                enhanced_info = self.structured_query(enhanced_cypher)[0][
                    "output"
                ]
                for prop in rel_props:
                    if prop["property"] in enhanced_info:
                        prop.update(enhanced_info[prop["property"]])
            except self.neo4j.exceptions.ClientError:
                # Sometimes the types are not consistent in the db
                pass

    # TODO(@antejavor): Implement the upsert_nodes
    def upsert_nodes(self, nodes: List[LabelledNode]) -> None:
        # Lists to hold separated types
        entity_dicts: List[dict] = []
        chunk_dicts: List[dict] = []

        # Sort by type
        for item in nodes:
            if isinstance(item, EntityNode):
                entity_dicts.append({**item.dict(), "id": item.id})
            elif isinstance(item, ChunkNode):
                chunk_dicts.append({**item.dict(), "id": item.id})
            else:
                # Log that we do not support these types of nodes
                # Or raise an error?
                pass

        if chunk_dicts:
            self.structured_query(
                """
                UNWIND $data AS row
                MERGE (c:Chunk {id: row.id})
                SET c.text = row.text
                WITH c, row
                SET c += row.properties
                WITH c, row.embedding AS embedding
                WHERE embedding IS NOT NULL
                CALL db.create.setNodeVectorProperty(c, 'embedding', embedding)
                RETURN count(*)
                """,
                param_map={"data": chunk_dicts},
            )

        if entity_dicts:
            self.structured_query(
                """
                UNWIND $data AS row
                MERGE (e:`__Entity__` {id: row.id})
                SET e += apoc.map.clean(row.properties, [], [])
                SET e.name = row.name
                WITH e, row
                CALL apoc.create.addLabels(e, [row.label])
                YIELD node
                WITH e, row
                CALL {
                    WITH e, row
                    WITH e, row
                    WHERE row.embedding IS NOT NULL
                    CALL db.create.setNodeVectorProperty(e, 'embedding', row.embedding)
                    RETURN count(*) AS count
                }
                WITH e, row WHERE row.properties.triplet_source_id IS NOT NULL
                MERGE (c:Chunk {id: row.properties.triplet_source_id})
                MERGE (e)<-[:MENTIONS]-(c)
                """,
                param_map={"data": entity_dicts},
            )

    # TODO(@DavIvek): Implement the upsert_relations
    def upsert_relations(self, relations: List[Relation]) -> None:
        """Add relations."""
        params = [r.dict() for r in relations]

        self.structured_query(
            """
            UNWIND $data AS row
            MERGE (source {id: row.source_id})
            MERGE (target {id: row.target_id})
            WITH source, target, row
            CALL apoc.merge.relationship(source, row.label, {}, row.properties, target) YIELD rel
            RETURN count(*)
            """,
            param_map={"data": params},
        )

    # TODO(@DavIvek): Implement the get
    def get(
        self,
        properties: Optional[dict] = None,
        ids: Optional[List[str]] = None,
    ) -> List[LabelledNode]:
        """Get nodes."""
        cypher_statement = "MATCH (e) "

        params = {}
        if properties or ids:
            cypher_statement += "WHERE "

        if ids:
            cypher_statement += "e.id in $ids "
            params["ids"] = ids

        if properties:
            prop_list = []
            for i, prop in enumerate(properties):
                prop_list.append(f"e.`{prop}` = $property_{i}")
                params[f"property_{i}"] = properties[prop]
            cypher_statement += " AND ".join(prop_list)

        return_statement = """
        WITH e
        RETURN e.id AS name,
               [l in labels(e) WHERE l <> '__Entity__' | l][0] AS type,
               e{.* , embedding: Null, id: Null} AS properties
        """
        cypher_statement += return_statement

        response = self.structured_query(cypher_statement, param_map=params)
        response = response if response else []

        nodes = []
        for record in response:
            # text indicates a chunk node
            # none on the type indicates an implicit node, likely a chunk node
            if "text" in record["properties"] or record["type"] is None:
                text = record["properties"].pop("text", "")
                nodes.append(
                    ChunkNode(
                        id_=record["name"],
                        text=text,
                        properties=remove_empty_values(record["properties"]),
                    )
                )
            else:
                nodes.append(
                    EntityNode(
                        name=record["name"],
                        label=record["type"],
                        properties=remove_empty_values(record["properties"]),
                    )
                )

        return nodes

    # TODO(@antejavor): Implement the get_triplets
    def get_triplets(
        self,
        entity_names: Optional[List[str]] = None,
        relation_names: Optional[List[str]] = None,
        properties: Optional[dict] = None,
        ids: Optional[List[str]] = None,
    ) -> List[Triplet]:
        # TODO: handle ids of chunk nodes
        cypher_statement = "MATCH (e:`__Entity__`) "

        params = {}
        if entity_names or properties or ids:
            cypher_statement += "WHERE "

        if entity_names:
            cypher_statement += "e.name in $entity_names "
            params["entity_names"] = entity_names

        if ids:
            cypher_statement += "e.id in $ids "
            params["ids"] = ids

        if properties:
            prop_list = []
            for i, prop in enumerate(properties):
                prop_list.append(f"e.`{prop}` = $property_{i}")
                params[f"property_{i}"] = properties[prop]
            cypher_statement += " AND ".join(prop_list)

        return_statement = f"""
        WITH e
        CALL {{
            WITH e
            MATCH (e)-[r{':`' + '`|`'.join(relation_names) + '`' if relation_names else ''}]->(t)
            RETURN e.name AS source_id, [l in labels(e) WHERE l <> '__Entity__' | l][0] AS source_type,
                   e{{.* , embedding: Null, name: Null}} AS source_properties,
                   type(r) AS type,
                   t.name AS target_id, [l in labels(t) WHERE l <> '__Entity__' | l][0] AS target_type,
                   t{{.* , embedding: Null, name: Null}} AS target_properties
            UNION ALL
            WITH e
            MATCH (e)<-[r{':`' + '`|`'.join(relation_names) + '`' if relation_names else ''}]-(t)
            RETURN t.name AS source_id, [l in labels(t) WHERE l <> '__Entity__' | l][0] AS source_type,
                   e{{.* , embedding: Null, name: Null}} AS source_properties,
                   type(r) AS type,
                   e.name AS target_id, [l in labels(e) WHERE l <> '__Entity__' | l][0] AS target_type,
                   t{{.* , embedding: Null, name: Null}} AS target_properties
        }}
        RETURN source_id, source_type, type, target_id, target_type, source_properties, target_properties"""
        cypher_statement += return_statement

        data = self.structured_query(cypher_statement, param_map=params)
        data = data if data else []

        triples = []
        for record in data:
            source = EntityNode(
                name=record["source_id"],
                label=record["source_type"],
                properties=remove_empty_values(record["source_properties"]),
            )
            target = EntityNode(
                name=record["target_id"],
                label=record["target_type"],
                properties=remove_empty_values(record["target_properties"]),
            )
            rel = Relation(
                source_id=record["source_id"],
                target_id=record["target_id"],
                label=record["type"],
            )
            triples.append([source, rel, target])
        return triples

    # TODO(@DavIvek): Implement the get_rel_map
    def get_rel_map(
        self,
        graph_nodes: List[LabelledNode],
        depth: int = 2,
        limit: int = 30,
        ignore_rels: Optional[List[str]] = None,
    ) -> List[Triplet]:
        """Get depth-aware rel map."""
        triples = []

        ids = [node.id for node in graph_nodes]
        # Needs some optimization
        response = self.structured_query(
            f"""
            MATCH (e:`__Entity__`)
            WHERE e.id in $ids
            MATCH p=(e)-[r*1..{depth}]-(other)
            WHERE ALL(rel in relationships(p) WHERE type(rel) <> 'MENTIONS')
            UNWIND relationships(p) AS rel
            WITH distinct rel
            WITH startNode(rel) AS source,
                type(rel) AS type,
                endNode(rel) AS endNode
            RETURN source.id AS source_id, [l in labels(source) WHERE l <> '__Entity__' | l][0] AS source_type,
                    source{{.* , embedding: Null, id: Null}} AS source_properties,
                    type,
                    endNode.id AS target_id, [l in labels(endNode) WHERE l <> '__Entity__' | l][0] AS target_type,
                    endNode{{.* , embedding: Null, id: Null}} AS target_properties
            LIMIT toInteger($limit)
            """,
            param_map={"ids": ids, "limit": limit},
        )
        response = response if response else []

        ignore_rels = ignore_rels or []
        for record in response:
            if record["type"] in ignore_rels:
                continue

            source = EntityNode(
                name=record["source_id"],
                label=record["source_type"],
                properties=remove_empty_values(record["source_properties"]),
            )
            target = EntityNode(
                name=record["target_id"],
                label=record["target_type"],
                properties=remove_empty_values(record["target_properties"]),
            )
            rel = Relation(
                source_id=record["source_id"],
                target_id=record["target_id"],
                label=record["type"],
            )
            triples.append([source, rel, target])

        return triples

    # TODO(@DavIvek): Implement the structured_query - I believe that we can use this one
    def structured_query(
        self, query: str, param_map: Optional[Dict[str, Any]] = None
    ) -> Any:
        param_map = param_map or {}

        with self._driver.session(database=self._database) as session:
            result = session.run(query, param_map)
            full_result = [d.data() for d in result]

        if self.sanitize_query_output:
            return value_sanitize(full_result)

        return full_result

    # TODO(@antejavor): Implement the vector_query
    def vector_query(
        self, query: VectorStoreQuery, **kwargs: Any
    ) -> Tuple[List[LabelledNode], List[float]]:
        """Query the graph store with a vector store query."""
        data = self.structured_query(
            """MATCH (e:`__Entity__`)
            WHERE e.embedding IS NOT NULL AND size(e.embedding) = $dimension
            WITH e, vector.similarity.cosine(e.embedding, $embedding) AS score
            ORDER BY score DESC LIMIT toInteger($limit)
            RETURN e.id AS name,
               [l in labels(e) WHERE l <> '__Entity__' | l][0] AS type,
               e{.* , embedding: Null, name: Null, id: Null} AS properties,
               score""",
            param_map={
                "embedding": query.query_embedding,
                "dimension": len(query.query_embedding),
                "limit": query.similarity_top_k,
            },
        )
        data = data if data else []

        nodes = []
        scores = []
        for record in data:
            node = EntityNode(
                name=record["name"],
                label=record["type"],
                properties=remove_empty_values(record["properties"]),
            )
            nodes.append(node)
            scores.append(record["score"])

        return (nodes, scores)

    # TODO(@antejavor): Implement the delete
    def delete(
        self,
        entity_names: Optional[List[str]] = None,
        relation_names: Optional[List[str]] = None,
        properties: Optional[dict] = None,
        ids: Optional[List[str]] = None,
    ) -> None:
        """Delete matching data."""
        if entity_names:
            self.structured_query(
                "MATCH (n) WHERE n.name IN $entity_names DETACH DELETE n",
                param_map={"entity_names": entity_names},
            )

        if ids:
            self.structured_query(
                "MATCH (n) WHERE n.id IN $ids DETACH DELETE n",
                param_map={"ids": ids},
            )

        if relation_names:
            for rel in relation_names:
                self.structured_query(f"MATCH ()-[r:`{rel}`]->() DELETE r")

        if properties:
            cypher = "MATCH (e) WHERE "
            prop_list = []
            params = {}
            for i, prop in enumerate(properties):
                prop_list.append(f"e.`{prop}` = $property_{i}")
                params[f"property_{i}"] = properties[prop]
            cypher += " AND ".join(prop_list)
            self.structured_query(
                cypher + " DETACH DELETE e", param_map=params
            )

    # TODO(@DavIvek): Implement the _enhanced_schema_cypher
    def _enhanced_schema_cypher(
        self,
        label_or_type: str,
        properties: List[Dict[str, Any]],
        exhaustive: bool,
        is_relationship: bool = False,
    ) -> str:
        if is_relationship:
            match_clause = f"MATCH ()-[n:`{label_or_type}`]->()"
        else:
            match_clause = f"MATCH (n:`{label_or_type}`)"

        with_clauses = []
        return_clauses = []
        output_dict = {}
        if exhaustive:
            for prop in properties:
                prop_name = prop["property"]
                prop_type = prop["type"]
                if prop_type == "STRING":
                    with_clauses.append(
                        f"collect(distinct substring(toString(n.`{prop_name}`), 0, 50)) "
                        f"AS `{prop_name}_values`"
                    )
                    return_clauses.append(
                        f"values:`{prop_name}_values`[..{DISTINCT_VALUE_LIMIT}],"
                        f" distinct_count: size(`{prop_name}_values`)"
                    )
                elif prop_type in [
                    "INTEGER",
                    "FLOAT",
                    "DATE",
                    "DATE_TIME",
                    "LOCAL_DATE_TIME",
                ]:
                    with_clauses.append(
                        f"min(n.`{prop_name}`) AS `{prop_name}_min`"
                    )
                    with_clauses.append(
                        f"max(n.`{prop_name}`) AS `{prop_name}_max`"
                    )
                    with_clauses.append(
                        f"count(distinct n.`{prop_name}`) AS `{prop_name}_distinct`"
                    )
                    return_clauses.append(
                        f"min: toString(`{prop_name}_min`), "
                        f"max: toString(`{prop_name}_max`), "
                        f"distinct_count: `{prop_name}_distinct`"
                    )
                elif prop_type == "LIST":
                    with_clauses.append(
                        f"min(size(n.`{prop_name}`)) AS `{prop_name}_size_min`, "
                        f"max(size(n.`{prop_name}`)) AS `{prop_name}_size_max`"
                    )
                    return_clauses.append(
                        f"min_size: `{prop_name}_size_min`, "
                        f"max_size: `{prop_name}_size_max`"
                    )
                elif prop_type in ["BOOLEAN", "POINT", "DURATION"]:
                    continue
                output_dict[prop_name] = "{" + return_clauses.pop() + "}"
        else:
            # Just sample 5 random nodes
            match_clause += " WITH n LIMIT 5"
            for prop in properties:
                prop_name = prop["property"]
                prop_type = prop["type"]

                # Check if indexed property, we can still do exhaustive
                prop_index = [
                    el
                    for el in self.structured_schema["metadata"]["index"]
                    if el["label"] == label_or_type
                    and el["properties"] == [prop_name]
                    and el["type"] == "RANGE"
                ]
                if prop_type == "STRING":
                    if (
                        prop_index
                        and prop_index[0].get("size") > 0
                        and prop_index[0].get("distinctValues")
                        <= DISTINCT_VALUE_LIMIT
                    ):
                        distinct_values = self.query(
                            f"CALL apoc.schema.properties.distinct("
                            f"'{label_or_type}', '{prop_name}') YIELD value"
                        )[0]["value"]
                        return_clauses.append(
                            f"values: {distinct_values},"
                            f" distinct_count: {len(distinct_values)}"
                        )
                    else:
                        with_clauses.append(
                            f"collect(distinct substring(n.`{prop_name}`, 0, 50)) "
                            f"AS `{prop_name}_values`"
                        )
                        return_clauses.append(f"values: `{prop_name}_values`")
                elif prop_type in [
                    "INTEGER",
                    "FLOAT",
                    "DATE",
                    "DATE_TIME",
                    "LOCAL_DATE_TIME",
                ]:
                    if not prop_index:
                        with_clauses.append(
                            f"collect(distinct toString(n.`{prop_name}`)) "
                            f"AS `{prop_name}_values`"
                        )
                        return_clauses.append(f"values: `{prop_name}_values`")
                    else:
                        with_clauses.append(
                            f"min(n.`{prop_name}`) AS `{prop_name}_min`"
                        )
                        with_clauses.append(
                            f"max(n.`{prop_name}`) AS `{prop_name}_max`"
                        )
                        with_clauses.append(
                            f"count(distinct n.`{prop_name}`) AS `{prop_name}_distinct`"
                        )
                        return_clauses.append(
                            f"min: toString(`{prop_name}_min`), "
                            f"max: toString(`{prop_name}_max`), "
                            f"distinct_count: `{prop_name}_distinct`"
                        )

                elif prop_type == "LIST":
                    with_clauses.append(
                        f"min(size(n.`{prop_name}`)) AS `{prop_name}_size_min`, "
                        f"max(size(n.`{prop_name}`)) AS `{prop_name}_size_max`"
                    )
                    return_clauses.append(
                        f"min_size: `{prop_name}_size_min`, "
                        f"max_size: `{prop_name}_size_max`"
                    )
                elif prop_type in ["BOOLEAN", "POINT", "DURATION"]:
                    continue

                output_dict[prop_name] = "{" + return_clauses.pop() + "}"

        with_clause = "WITH " + ",\n     ".join(with_clauses)
        return_clause = (
            "RETURN {"
            + ", ".join(f"`{k}`: {v}" for k, v in output_dict.items())
            + "} AS output"
        )

        # Combine all parts of the Cypher query
        return f"{match_clause}\n{with_clause}\n{return_clause}"

    # TODO(@DavIvek): Implement the get_schema
    def get_schema(self, refresh: bool = False) -> Any:
        if refresh:
            self.refresh_schema()

        return self.structured_schema

    # TODO(@DavIvek): Implement the get_schema_str
    def get_schema_str(self, refresh: bool = False) -> str:
        schema = self.get_schema(refresh=refresh)

        formatted_node_props = []
        formatted_rel_props = []

        if self.enhcnaced_schema:
            # Enhanced formatting for nodes
            for node_type, properties in schema["node_props"].items():
                formatted_node_props.append(f"- **{node_type}**")
                for prop in properties:
                    example = ""
                    if prop["type"] == "STRING" and prop.get("values"):
                        if (
                            prop.get("distinct_count", 11)
                            > DISTINCT_VALUE_LIMIT
                        ):
                            example = (
                                f'Example: "{clean_string_values(prop["values"][0])}"'
                                if prop["values"]
                                else ""
                            )
                        else:  # If less than 10 possible values return all
                            example = (
                                (
                                    "Available options: "
                                    f'{[clean_string_values(el) for el in prop["values"]]}'
                                )
                                if prop["values"]
                                else ""
                            )

                    elif prop["type"] in [
                        "INTEGER",
                        "FLOAT",
                        "DATE",
                        "DATE_TIME",
                        "LOCAL_DATE_TIME",
                    ]:
                        if prop.get("min") is not None:
                            example = f'Min: {prop["min"]}, Max: {prop["max"]}'
                        else:
                            example = (
                                f'Example: "{prop["values"][0]}"'
                                if prop.get("values")
                                else ""
                            )
                    elif prop["type"] == "LIST":
                        # Skip embeddings
                        if (
                            not prop.get("min_size")
                            or prop["min_size"] > LIST_LIMIT
                        ):
                            continue
                        example = f'Min Size: {prop["min_size"]}, Max Size: {prop["max_size"]}'
                    formatted_node_props.append(
                        f"  - `{prop['property']}`: {prop['type']} {example}"
                    )

            # Enhanced formatting for relationships
            for rel_type, properties in schema["rel_props"].items():
                formatted_rel_props.append(f"- **{rel_type}**")
                for prop in properties:
                    example = ""
                    if prop["type"] == "STRING":
                        if (
                            prop.get("distinct_count", 11)
                            > DISTINCT_VALUE_LIMIT
                        ):
                            example = (
                                f'Example: "{clean_string_values(prop["values"][0])}"'
                                if prop.get("values")
                                else ""
                            )
                        else:  # If less than 10 possible values return all
                            example = (
                                (
                                    "Available options: "
                                    f'{[clean_string_values(el) for el in prop["values"]]}'
                                )
                                if prop.get("values")
                                else ""
                            )
                    elif prop["type"] in [
                        "INTEGER",
                        "FLOAT",
                        "DATE",
                        "DATE_TIME",
                        "LOCAL_DATE_TIME",
                    ]:
                        if prop.get("min"):  # If we have min/max
                            example = (
                                f'Min: {prop["min"]}, Max:  {prop["max"]}'
                            )
                        else:  # return a single value
                            example = (
                                f'Example: "{prop["values"][0]}"'
                                if prop.get("values")
                                else ""
                            )
                    elif prop["type"] == "LIST":
                        # Skip embeddings
                        if prop["min_size"] > LIST_LIMIT:
                            continue
                        example = f'Min Size: {prop["min_size"]}, Max Size: {prop["max_size"]}'
                    formatted_rel_props.append(
                        f"  - `{prop['property']}: {prop['type']}` {example}"
                    )
        else:
            # Format node properties
            for label, props in schema["node_props"].items():
                props_str = ", ".join(
                    [f"{prop['property']}: {prop['type']}" for prop in props]
                )
                formatted_node_props.append(f"{label} {{{props_str}}}")

            # Format relationship properties using structured_schema
            for type, props in schema["rel_props"].items():
                props_str = ", ".join(
                    [f"{prop['property']}: {prop['type']}" for prop in props]
                )
                formatted_rel_props.append(f"{type} {{{props_str}}}")

        # Format relationships
        formatted_rels = [
            f"(:{el['start']})-[:{el['type']}]->(:{el['end']})"
            for el in schema["relationships"]
        ]

        return "\n".join(
            [
                "Node properties:",
                "\n".join(formatted_node_props),
                "Relationship properties:",
                "\n".join(formatted_rel_props),
                "The relationships:",
                "\n".join(formatted_rels),
            ]
        )

    # TODO(@antejavor): Check if this is needed
    def update_extraction_prompt(
        self,
        prompt_provider: PromptProvider,
        entity_types: list[EntityType],
        relations: list[Relation],
    ):
        # Fetch the kg extraction prompt with blank entity types and relations
        # Note - Assumes that for given prompt there is a `_with_spec` that can have entities + relations specified
        few_shot_ner_kg_extraction_with_spec = prompt_provider.get_prompt(
            f"{self.config.kg_extraction_prompt}_with_spec"
        )

        # Format the prompt to include the desired entity types and relations
        few_shot_ner_kg_extraction = (
            few_shot_ner_kg_extraction_with_spec.replace(
                "{entity_types}", format_entity_types(entity_types)
            ).replace("{relations}", format_relations(relations))
        )

        # Update the "few_shot_ner_kg_extraction" prompt used in downstream KG construction
        prompt_provider.update_prompt(
            self.config.kg_extraction_prompt,
            json.dumps(few_shot_ner_kg_extraction, ensure_ascii=False),
        )

    def update_kg_search_prompt(
        self,
        prompt_provider: PromptProvider,
        entity_types: list[EntityType],
        relations: list[Relation],
    ):
        # Fetch the kg extraction prompt with blank entity types and relations
        # Note - Assumes that for given prompt there is a `_with_spec` that can have entities + relations specified
        few_shot_ner_kg_extraction_with_spec = prompt_provider.get_prompt(
            f"{self.config.kg_search_prompt}_with_spec"
        )

        # Format the prompt to include the desired entity types and relations
        few_shot_ner_kg_extraction = (
            few_shot_ner_kg_extraction_with_spec.replace(
                "{entity_types}",
                format_entity_types(entity_types, ignore_subcats=True),
            ).replace("{relations}", format_relations(relations))
        )

        # Update the "few_shot_ner_kg_extraction" prompt used in downstream KG construction
        prompt_provider.update_prompt(
            self.config.kg_search_prompt,
            json.dumps(few_shot_ner_kg_extraction, ensure_ascii=False),
        )
