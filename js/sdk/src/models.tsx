export interface TokenInfo {
  token: string;
}

export interface LoginResponse {
  results: {
    access_token: TokenInfo;
    refresh_token: TokenInfo;
  };
}

export interface RefreshTokenResponse {
  results: {
    access_token: { token: string };
    refresh_token: { token: string };
  };
}

export interface GenerationConfig {
  model?: string;
  temperature?: number;
  top_p?: number;
  max_tokens_to_sample?: number;
  stream?: boolean;
  functions?: Array<Record<string, any>>;
  tools?: Array<Record<string, any>>;
  add_generation_kwargs?: Record<string, any>;
  api_base?: string;
}

export interface HybridSearchSettings {
  full_text_weight: number;
  semantic_weight: number;
  full_text_limit: number;
  rrf_k: number;
}

export interface VectorSearchSettings {
  use_vector_search?: boolean;
  use_hybrid_search?: boolean;
  filters?: Record<string, any>;
  search_limit?: number;
  selected_group_ids?: string[];
  index_measure: IndexMeasure;
  include_values?: boolean;
  include_metadatas?: boolean;
  probes?: number;
  ef_search?: number;
  search_strategy?: string;
  hybrid_search_settings?: HybridSearchSettings;
}

export interface KGSearchSettings {
  use_kg_search?: boolean;
  kg_search_type?: "global" | "local";
  kg_search_level?: number | null;
  kg_search_generation_config?: GenerationConfig;
  entity_types?: any[];
  relationships?: any[];
  max_community_description_length?: number;
  max_llm_queries_for_global_search?: number;
  local_search_limits?: Record<string, number>;
}

export interface KGLocalSearchResult {
  query: string;
  entities: Record<string, any>;
  relationships: Record<string, any>;
  communities: Record<string, any>;
}

export interface KGGlobalSearchResult {
  query: string;
  search_result: string[];
}

export interface KGSearchResult {
  local_result?: KGLocalSearchResult;
  global_result?: KGGlobalSearchResult;
}



export interface Message {
  role: string;
  content: string;
}

export interface R2RDocumentChunksRequest {
  document_id: string;
}

export enum IndexMeasure {
  COSINE_DISTANCE = "cosine_distance",
  L2_DISTANCE = "l2_distance",
  MAX_INNER_PRODUCT = "max_inner_product",
}
