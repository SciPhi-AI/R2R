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
    RelationshipType,
    format_entity_types,
    format_relations,
    Community,
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
        self.paths = {'graph_root': self.kg_store_path}
        cache_paths = ['entities', 'triples', 'communities', 'entities_with_description']
        for path in cache_paths:
            self.paths[path] = os.path.join(self.kg_store_path, path)
            os.makedirs(self.paths[path], exist_ok=True)

        self.cached_entities = {}
        self.cached_triples = {}
        self.cached_communities = {}

    def check_cache(self, cache_type: str, cache_id: str) -> bool:
        if cache_type == 'entity':
            return os.path.exists(os.path.join(self.paths['entities'], f"{cache_id}.pkl"))
        elif cache_type == 'triple':
            return os.path.exists(os.path.join(self.paths['triples'], f"{cache_id}.pkl"))
        else:
            return False
    
    def upsert_nodes_and_relationships(self, kg_extractions: list[KGExtraction]) -> None:

        all_entities = []
        all_relationships = []
        for extraction in kg_extractions:
            all_entities.extend(extraction.entities)
            all_relationships.extend(extraction.triples)

        nodes_upserted = self.upsert_nodes(all_entities)
        relationships_upserted = self.upsert_relations(all_relationships)

        return nodes_upserted, relationships_upserted
    

    def get_communities(self) -> List[Community]:
        communities = []
        for community_id in os.listdir(self.paths['communities']):
            filepath = os.path.join(self.paths['communities'], community_id)
            with open(filepath, 'rb') as f:
                community = pickle.load(f)
                communities.append(community)
        return communities


    def upsert_communities(self, communities: List[Community], *args, **kwargs) -> Any:
        for community in communities:
            filepath = os.path.join(self.paths['communities'], f"{community.id}.pkl")
            with open(filepath, 'wb') as f:
                pickle.dump(community, f)


    def upsert_entities(self, entities: List[Entity], *args, **kwargs) -> Any:

        # Ensure the directory exists
        if 'with_description' in kwargs and kwargs['with_description']:
            path = self.paths['entities_with_description']
        else:
            path = self.paths['entities']

        # Save each entity as a pickle file
        for entity in entities:
            filepath = os.path.join(path, f"{entity.id}.pkl")
            with open(filepath, 'wb') as f:
                pickle.dump(entity, f)

    def retrieve_cache(self, cache_type: str, cache_id: str) -> bool:
        filepath = os.path.join(self.paths[cache_type], f"{cache_id}.pkl")
        if os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                return pickle.load(f)
        else:
            return None

    def upsert_triples(self, triples: List[Triple]) -> None:

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
                if entity_name is None or entity.value == entity_name:
                    entities.append(entity)
        return entities
    

    def get_entity_map(self, entity_names: list[str] | None = None) -> dict[str, list[Any]]:
        # returns a dictionary
        # keys are entity values
        # values contain dictionary of entities and triples

        entities = self.get(entity_names)
        triples = self.get_triples(entity_names)
        entity_map = {}
        for entity in entities:
            if entity.id not in entity_map:
                entity_map[entity.value] = {'entities': [], 'triples': []}
            entity_map[entity.value]['entities'].append(entity)

        for triple in triples:
            if triple.subject in entity_map:
                entity_map[triple.subject]['triples'].append(triple)
            if triple.object in entity_map:
                entity_map[triple.object]['triples'].append(triple)
        return entity_map
    

    def get_entities(self, entity_ids: list[str] | None = None, with_description: bool = False) -> list[Entity]:
        
        if with_description:
            path = self.paths['entities_with_description']
        else:
            path = self.paths['entities']
        
        entities = []
        for entity_id in os.listdir(path):
            filepath = os.path.join(path, entity_id)
            with open(filepath, 'rb') as f:
                entity = pickle.load(f)
                if entity_ids is None or entity.id in entity_ids:
                    entities.append(entity)
        return entities
    
    def get_triples(self, triple_ids: list[str] | None = None) -> list[Triple]:
        triples = []
        for triple_id in os.listdir(self.paths['triples']):
            filepath = os.path.join(self.paths['triples'], triple_id)
            with open(filepath, 'rb') as f:
                triple = pickle.load(f)
                if triple_ids is None or triple.id in triple_ids:
                    triples.append(triple)
        return triples

        # returns a dictionary
        # keys are entity values
        # values contain dictionary of entities and triples

        entities = self.get(entity_names)
        triples = self.get_triples(entity_names)
        entity_map = {}
        for entity in entities:
            if entity.id not in entity_map:
                entity_map[entity.value] = {'entities': [], 'triples': []}
            entity_map[entity.value]['entities'].append(entity)

        for triple in triples:
            if triple.subject in entity_map:
                entity_map[triple.subject]['triples'].append(triple)
            if triple.object in entity_map:
                entity_map[triple.object]['triples'].append(triple)
        return entity_map

    def get_triples(self, entity_names: List[str] = None) -> List[Triple]:
        triples = []
        for triple_id in os.listdir(self.paths['triples']):
            filepath = os.path.join(self.paths['triples'], triple_id)
            with open(filepath, 'rb') as f:
                triple = pickle.load(f)
                if entity_names is None or triple.subject in entity_names or triple.object in entity_names:
                    triples.append(triple)
        return triples
    

    def get_communities(self, level = None) -> List[Community]:
        communities = []
        for community_id in os.listdir(self.paths['communities']):
            filepath = os.path.join(self.paths['communities'], community_id)
            if level is None or community_id.split('_')[0] == str(level):
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


    def update_extraction_prompt(self, prompt_provider: Any, entity_types: list[Any], relations: list[RelationshipType]):
        return super().update_extraction_prompt(prompt_provider, entity_types, relations)
    
    def update_kg_search_prompt(self, prompt_provider: Any, entity_types: list[Any], relations: list[RelationshipType]):
        return super().update_kg_search_prompt(prompt_provider, entity_types, relations)
    
    def vector_search(self, query) -> Tuple[List, List[float]]:
        return super().vector_search(query)
    
    def get_rel_map(self, subjs: list[str] | None = None, depth: int = 2, limit: int = 30) -> dict[str, list[list[str]]]:
        pass

    def get_schema(self) -> dict[str, Any]:
        pass

    def vector_query(self, query, **kwargs: Any) -> Tuple[list[Entity], list[float]]:
        pass