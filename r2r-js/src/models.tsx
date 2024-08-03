export interface UserCreate {
  email: string;
  password: string;
}

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

export const DEFAULT_GENERATION_CONFIG: GenerationConfig = {
  temperature: 0.1,
  top_p: 1,
  top_k: 100,
  max_tokens_to_sample: 1024,
  model: "gpt-4o",
  stream: true,
};

export interface VectorSearchSettings {
  use_vector_search: boolean;
  search_filters?: Record<string, any>;
  search_limit: number;
  do_hybrid_search: boolean;
}

export interface KGSearchSettings {
  use_kg_search: boolean;
  agent_generation_config?: Record<string, any>;
}

export interface Message {
  role: string;
  content: string;
}

export interface R2RUpdatePromptRequest {
  name: string;
  template?: string;
  input_types?: Record<string, string>;
}

export interface R2RIngestFilesRequest {
  metadatas?: Record<string, any>[];
  document_ids?: string[];
  user_ids?: (string | null)[];
  versions?: string[];
  skip_document_info?: boolean;
}

export interface R2RUpdateFilesRequest {
  metadatas?: Record<string, any>[];
  document_ids?: string[];
}

export interface R2RSearchRequest {
  query: string;
  vector_search_settings: VectorSearchSettings;
  kg_search_settings: KGSearchSettings;
}

export interface R2RRAGRequest {
  query: string;
  vector_search_settings: Record<string, any>;
  kg_search_settings: Record<string, any>;
  rag_generation_config?: Record<string, any>;
}

export interface R2RDeleteRequest {
  keys: string[];
  values: (boolean | number | string)[];
}

export interface FilterCriteria {
  filters?: { [key: string]: string };
}

export interface AnalysisTypes {
  analysis_types?: { [key: string]: string[] };
}

export interface R2RAnalyticsRequest {
  filter_criteria: FilterCriteria;
  analysis_types: AnalysisTypes;
}

export interface R2RUsersOverviewRequest {
  user_ids?: string[];
}

export interface R2RDocumentsOverviewRequest {
  document_ids?: string[];
  user_ids?: string[];
}

export interface R2RDocumentChunksRequest {
  document_id: string;
}

export interface R2RLogsRequest {
  log_type_filter?: string | null;
  max_runs_requested: number;
}

export interface R2RAgentRequest {
  messages: Message[];
  vector_search_settings?: {
    use_vector_search: boolean;
    search_filters?: Record<string, any>;
    search_limit: number;
    do_hybrid_search: boolean;
  };
  kg_search_settings?: {
    use_kg_search: boolean;
    kg_search_generation_config?: Record<string, any>;
  };
  rag_generation_config?: GenerationConfig;
  task_prompt_override?: string;
  include_title_if_available?: boolean;
}

export interface R2RPrintRelationshipRequest {
  limit: number;
}
