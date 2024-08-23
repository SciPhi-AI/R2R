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
  temperature?: number;
  top_p?: number;
  top_k?: number;
  max_tokens_to_sample?: number;
  model?: string;
  stream?: boolean;
  functions?: Array<Record<string, any>>;
  skip_special_tokens?: boolean;
  stop_token?: string;
  num_beams?: number;
  do_sample?: boolean;
  generate_with_chat?: boolean;
  add_generation_kwargs?: Record<string, any>;
  api_base?: string;
}

export interface VectorSearchSettings {
  use_vector_search?: boolean;
  filters?: Record<string, any>;
  search_limit?: number;
  use_hybrid_search?: boolean;
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
  entities: any[];
  relationships: any[];
  communities: any[];
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
