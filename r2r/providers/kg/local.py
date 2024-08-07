# implementing a local knowledge graphs. Everything is stored in pkl files

import json
import os
import pickle
from typing import Any, Dict, List, Optional, Tuple

from r2r.base import (
    EntityType,
    KGConfig,
    KGProvider,
    PromptProvider,
    Relation,
    format_entity_types,
    format_relations,
    Community,
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

from r2r.base.abstractions.graph import (
    Entity,
    Triple,
    KGExtraction,
)

class LocalKGProvider(KGProvider):

    def __init__(self, config: KGConfig):
        super().__init__(config)

      
        if config.kg_store_path is None:    
            self.kg_store_path = os.path.join(os.environ['HOME'], ".graph_data")
        else:
            self.kg_store_path = config.kg_store_path

        os.makedirs(self.kg_store_path, exist_ok=True)
        for path in ['entities', 'triples', 'communities']:
            os.makedirs(os.path.join(self.kg_store_path, path), exist_ok=True)

        self.paths = {
            'graph_root': self.kg_store_path,
            'entities': os.path.join(self.kg_store_path, "entities"),
            'triples': os.path.join(self.kg_store_path, "triples"),
            'communities': os.path.join(self.kg_store_path, "communities"),
        }

        self.cached_entities = {}
        self.cached_triples = {}
        self.cached_communities = {}
    
    def upsert_nodes_and_relationships(self, kg_extractions: list[KGExtraction]) -> None:

        all_entities = []
        all_relationships = []
        for extraction in kg_extractions:
            all_entities.extend(extraction.entities)
            all_relationships.extend(extraction.triples)

        nodes_upserted = self.upsert_nodes(all_entities)
        relationships_upserted = self.upsert_relations(all_relationships)

        return nodes_upserted, relationships_upserted

    def upsert_nodes(self, entities: List[Entity]) -> Any:

        # Ensure the directory exists
        os.makedirs(self.kg_store_path, exist_ok=True)

        # Save each entity as a pickle file
        for entity in entities:
            filepath = os.path.join(self.paths['entities'], f"{entity.id}_{entity.value}.pkl")
            with open(filepath, 'wb') as f:
                pickle.dump(entity, f)


    def upsert_relations(self, triples: List[Triple]) -> None:

        for triple in triples:
            filepath = os.path.join(self.paths['triples'], f"{triple.id}.pkl")
            with open(filepath, 'wb') as f:
                pickle.dump(triple, f)


    def get(self, entity_name: str = None) -> Entity:
        entities = []
        for entity_id in os.listdir(self.paths['entities']):
            filepath = os.path.join(self.paths['entities'], entity_id)
            with open(filepath, 'rb') as f:
                entity = pickle.load(f)
                if entity_name is None or entity.name == entity_name:
                    entities.append(entity)
        return entities

    def get_triplets(self, entity_names: List[str] = None) -> List[Triple]:
        triples = []
        for triple_id in os.listdir(self.paths['triples']):
            filepath = os.path.join(self.paths['triples'], triple_id)
            with open(filepath, 'rb') as f:
                triple = pickle.load(f)
                if entity_names is None or triple.source_id in entity_names or triple.target_id in entity_names:
                    triples.append(triple)
        return triples
    

    def get_communities(self) -> List[Community]:
        communities = []
        for community_id in os.listdir(self.paths['communities']):
            filepath = os.path.join(self.paths['communities'], community_id)
            with open(filepath, 'rb') as f:
                community = pickle.load(f)
                communities.append(community)
        return communities
    

    def client(self) -> Any:
        return self
    

    def delete(self, 
               entity_names: List[str] = None, 
               relation_names: List[str] = None, 
               properties: Dict[str, Any] = None, 
               ids: List[str] = None) -> None:
        pass

    def structured_query(self, query: str, param_map: Dict[str, Any]) -> Any:
        pass


    def update_extraction_prompt(self, prompt_provider: Any, entity_types: list[Any], relations: list[Relation]):
        return super().update_extraction_prompt(prompt_provider, entity_types, relations)
    
    def update_kg_search_prompt(self, prompt_provider: Any, entity_types: list[Any], relations: list[Relation]):
        return super().update_kg_search_prompt(prompt_provider, entity_types, relations)
    
    def vector_search(self, query: VectorStoreQuery) -> Tuple[List[EntityNode], List[float]]:
        return super().vector_search(query)
    
    def get_rel_map(self, subjs: list[str] | None = None, depth: int = 2, limit: int = 30) -> dict[str, list[list[str]]]:
        pass

    def get_schema(self) -> dict[str, Any]:
        pass

    def vector_query(self, query: VectorStoreQuery, **kwargs: Any) -> Tuple[list[LabelledNode], list[float]]:
        pass