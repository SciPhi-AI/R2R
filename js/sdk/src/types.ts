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

// System types
export interface SettingsResponse {
  config: Record<string, any>;
  prompts: Record<string, any>;
  r2r_project_name: string;
}

// User types
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

// Ingestion Responses
export type WrappedIngestionResponse = ResultsWrapper<IngestionResponse>;
export type WrappedMetadataUpdateResponse = ResultsWrapper<IngestionResponse>;
export type WrappedUpdateResponse = ResultsWrapper<UpdateResponse>;
export type WrappedListVectorIndicesResponse = ResultsWrapper<IndexConfig[]>;

// Prompt Responses
export type WrappedPromptResponse = ResultsWrapper<PromptResponse>;
export type WrappedPromptsResponse = PaginatedResultsWrapper<PromptResponse[]>;

// System Responses
export type WrappedSettingsResponse = ResultsWrapper<SettingsResponse>;

// User Responses
export type WrappedUserResponse = ResultsWrapper<UserResponse>;
export type WrappedUsersResponse = PaginatedResultsWrapper<UserResponse[]>;
