export interface UnprocessedChunk {
  id: string;
  document_id?: string;
  collection_ids: string[];
  metadata: Record<string, any>;
  text: string;
}

// Response wrappers
export interface ResultsWrapper<T> {
  results: T;
}

export interface PaginatedResultsWrapper<T> extends ResultsWrapper<T> {
  total_entries: number;
}

// Generic response types
export interface GenericBooleanResponse {
  success: boolean;
}

export interface GenericMessageResponse {
  message: string;
}

// Chunk types
export interface ChunkResponse {
  id: string;
  document_id: string;
  user_id: string;
  collection_ids: string[];
  text: string;
  metadata: Record<string, any>;
  vector?: any;
}

// Collection types
export interface CollectionResponse {
  id: string;
  owner_id?: string;
  name: string;
  description?: string;
  graph_cluster_status: string;
  graph_sync_status: string;
  created_at: string;
  updated_at: string;
  user_count: number;
  document_count: number;
}

// Community types
export interface CommunityResponse {
  id: string;
  name: string;
  summary: string;
  findings: string[];
  communityId?: string;
  graphId?: string;
  collectionId?: string;
  rating?: number;
  ratingExplanation?: string;
  descriptionEmbedding?: string;
}

// Conversation types
export interface ConversationResponse {
  id: string;
  created_at: string;
  user_id?: string;
  name?: string;
}

export interface MessageResponse {
  id: string;
  message: any;
  metadata: Record<string, any>;
}

// Document types
export interface DocumentResponse {
  id: string;
  collection_ids: string[];
  owner_id: string;
  document_type: string;
  metadata: Record<string, any>;
  title?: string;
  version: string;
  size_in_bytes?: number;
  ingestion_status: string;
  extraction_status: string;
  created_at: string;
  updated_at: string;
  ingestion_attempt_number?: number;
  summary?: string;
  summary_embedding?: string;
}

// Entity types
export interface EntityResponse {
  id: string;
  name: string;
  description?: string;
  category?: string;
  metadata: Record<string, any>;
  parent_id?: string;
  chunk_ids?: string[];
  description_embedding?: string;
}

// Graph types
export interface GraphResponse {
  id: string;
  user_id: string;
  name: string;
  description: string;
  status: string;
  created_at: string;
  updated_at: string;
}

// Index types
export enum IndexMeasure {
  COSINE_DISTANCE = "cosine_distance",
  L2_DISTANCE = "l2_distance",
  MAX_INNER_PRODUCT = "max_inner_product",
}

// Ingestion types
export interface IngestionResponse {
  message: string;
  task_id?: string;
  document_id: string;
}

export interface UpdateResponse {
  message: string;
  task_id?: string;
  document_id: string;
}

export interface IndexConfig {
  name?: string;
  table_name?: string;
  index_method?: string;
  index_measure?: string;
  index_arguments?: string;
  index_name?: string;
  index_column?: string;
  concurrently?: boolean;
}

// Prompt types
export interface PromptResponse {
  id: string;
  name: string;
  template: string;
  created_at: string;
  updated_at: string;
  input_types: string[];
}

// Relationship types
export interface RelationshipResponse {
  id: string;
  subject: string;
  predicate: string;
  object: string;
  description?: string;
  subject_id: string;
  object_id: string;
  weight: number;
  chunk_ids: string[];
  parent_id: string;
  metadata: Record<string, any>;
}

// Retrieval types
export interface ChunkSearchSettings {
  index_measure?: IndexMeasure;
  probes?: number;
  ef_search?: number;
  enabled?: boolean;
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
  response_format?: string;
}

export interface HybridSearchSettings {
  full_text_weight?: number;
  semantic_weight?: number;
  full_text_limit?: number;
  rrf_k?: number;
}

export interface GraphSearchSettings {
  generation_config?: GenerationConfig;
  graphrag_map_system?: string;
  graphrag_reduce_system?: string;
  max_community_description_length?: number;
  max_llm_queries_for_global_search?: number;
  limits?: Record<string, any>;
  enabled?: boolean;
}

export interface SearchSettings {
  use_hybrid_search?: boolean;
  use_semantic_search?: boolean;
  use_full_text_search?: boolean;
  filters?: Record<string, any>;
  limit?: number;
  offset?: number;
  include_metadata?: boolean;
  include_scores?: boolean;
  search_strategy?: string;
  hybrid_settings?: HybridSearchSettings;
  chunk_settings?: ChunkSearchSettings;
  graph_settings?: GraphSearchSettings;
}
export interface VectorSearchResult {
  chunk_id: string;
  document_id: string;
  user_id: string;
  collection_ids: string[];
  score: number;
  text: string;
  metadata?: Record<string, any>;
}

export type KGSearchResultType =
  | "entity"
  | "relationship"
  | "community"
  | "global";

export interface GraphSearchResult {
  content: any;
  result_type?: KGSearchResultType;
  chunk_ids?: string[];
  metadata: Record<string, any>;
  score?: number;
}

export interface CombinedSearchResponse {
  chunk_search_results: VectorSearchResult[];
  graph_search_results?: GraphSearchResult[];
}

// System types

export interface ServerStats {
  start_time: string;
  uptime_seconds: number;
  cpu_usage: number;
  memory_usage: number;
}

export interface SettingsResponse {
  config: Record<string, any>;
  prompts: Record<string, any>;
  r2r_project_name: string;
}

// User types

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
}

export interface User {
  id: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
  updated_at: string;
  is_verified: boolean;
  collection_ids: string[];
  hashed_password?: string;
  verification_code_expiry?: string;
  name?: string;
  bio?: string;
  profile_picture?: string;
}

// Generic Responses
export type WrappedBooleanResponse = ResultsWrapper<GenericBooleanResponse>;
export type WrappedGenericMessageResponse =
  ResultsWrapper<GenericMessageResponse>;

// Chunk Responses
export type WrappedChunkResponse = ResultsWrapper<ChunkResponse>;
export type WrappedChunksResponse = PaginatedResultsWrapper<ChunkResponse[]>;

// Collection Responses
export type WrappedCollectionResponse = ResultsWrapper<CollectionResponse>;
export type WrappedCollectionsResponse = PaginatedResultsWrapper<
  CollectionResponse[]
>;

// Community Responses
export type WrappedCommunityResponse = ResultsWrapper<CommunityResponse>;
export type WrappedCommunitiesResponse = PaginatedResultsWrapper<
  CommunityResponse[]
>;

// Conversation Responses
export type WrappedConversationMessagesResponse = ResultsWrapper<
  MessageResponse[]
>;
export type WrappedConversationResponse =
  PaginatedResultsWrapper<ConversationResponse>;
export type WrappedConversationsResponse = PaginatedResultsWrapper<
  ConversationResponse[]
>;
export type WrappedMessageResponse = ResultsWrapper<MessageResponse>;
export type WrappedMessagesResponse = PaginatedResultsWrapper<
  MessageResponse[]
>;

// Document Responses
export type WrappedDocumentResponse = ResultsWrapper<DocumentResponse>;
export type WrappedDocumentsResponse = PaginatedResultsWrapper<
  DocumentResponse[]
>;

// Entity Responses
export type WrappedEntityResponse = ResultsWrapper<EntityResponse>;
export type WrappedEntitiesResponse = PaginatedResultsWrapper<EntityResponse[]>;

// Graph Responses
export type WrappedGraphResponse = ResultsWrapper<GraphResponse>;
export type WrappedGraphsResponse = PaginatedResultsWrapper<GraphResponse[]>;

// Ingestion Responses
export type WrappedIngestionResponse = ResultsWrapper<IngestionResponse>;
export type WrappedMetadataUpdateResponse = ResultsWrapper<IngestionResponse>;
export type WrappedUpdateResponse = ResultsWrapper<UpdateResponse>;
export type WrappedListVectorIndicesResponse = ResultsWrapper<IndexConfig[]>;

// Prompt Responses
export type WrappedPromptResponse = ResultsWrapper<PromptResponse>;
export type WrappedPromptsResponse = PaginatedResultsWrapper<PromptResponse[]>;

// Relationship Responses
export type WrappedRelationshipResponse = ResultsWrapper<RelationshipResponse>;
export type WrappedRelationshipsResponse = PaginatedResultsWrapper<
  RelationshipResponse[]
>;

// Retrieval Responses
export type WrappedVectorSearchResponse = ResultsWrapper<VectorSearchResult[]>;
export type WrappedSearchResponse = ResultsWrapper<CombinedSearchResponse>;

// System Responses
export type WrappedSettingsResponse = ResultsWrapper<SettingsResponse>;
export type WrappedServerStatsResponse = ResultsWrapper<ServerStats>;

// User Responses
export type WrappedTokenResponse = ResultsWrapper<TokenResponse>;
export type WrappedUserResponse = ResultsWrapper<User>;
export type WrappedUsersResponse = PaginatedResultsWrapper<User[]>;
