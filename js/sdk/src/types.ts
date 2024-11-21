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
  user_id?: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  user_count: number;
  document_count: number;
}

//TODO: Sync this with the finished API response model
// Community types
export interface CommunityResponse {}

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

export interface BranchResponse {
  branch_id: string;
  branch_point_id?: string;
  content?: string;
  created_at: string;
  user_id?: string;
  name?: string;
}

// Document types
export interface DocumentResponse {
  id: string;
  collection_ids: string[];
  user_id: string;
  document_type: string;
  metadata: Record<string, any>;
  title?: string;
  version: string;
  size_in_bytes?: number;
  ingestion_status: string;
  kg_extraction_status: string;
  created_date: string;
  updated_date: string;
  ingestion_attempt_number?: number;
  summary?: string;
  summary_embedding?: string;
}

// Entity types
export interface EntityResponse {
  id: string;
  sid?: string;
  name: string;
  category?: string;
  description?: string;
  chunk_ids: string[];
  description_embedding?: string;
  document_id: string;
  document_ids: string[];
  graph_ids: string[];
  user_id: string;
  last_modified_by: string;
  created_at: string;
  updated_at: string;
  attributes?: Record<string, any>;
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

//TODO: Sync this with the finished API response model
// Relationship types
export interface RelationshipResponse {}

// Retrieval types
export interface VectorSearchResult {
  chunk_id: string;
  document_id: string;
  user_id: string;
  collection_ids: string[];
  score: number;
  text: string;
  metadata?: Record<string, any>;
}

export interface KGSearchResult {
  method: string;
  content: string;
  result_type?: string;
  chunks_ids?: string[];
  metadata?: Record<string, any>;
}

export interface CombinedSearchResponse {
  vector_search_results: VectorSearchResult[];
  graph_search_results?: KGSearchResult[];
}

// System types
export interface LogsResponse {
  run_id: string;
  run_type: string;
  entries: Record<string, any>[];
  timestamp?: string;
  user_id?: string;
}

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

export interface UserResponse {
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
export type WrappedBranchResponse = ResultsWrapper<BranchResponse>;
export type WrappedBranchesResponse = PaginatedResultsWrapper<BranchResponse[]>;

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
export type WrappedLogsResponse = PaginatedResultsWrapper<LogsResponse[]>;
export type WrappedServerStatsResponse = ResultsWrapper<ServerStats>;

// User Responses
export type WrappedTokenResponse = ResultsWrapper<TokenResponse>;
export type WrappedUserResponse = ResultsWrapper<UserResponse>;
export type WrappedUsersResponse = PaginatedResultsWrapper<UserResponse[]>;
