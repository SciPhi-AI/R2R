export interface UnprocessedChunk {
  id: string;
  documentId?: string;
  collectionIds: string[];
  metadata: Record<string, any>;
  text: string;
}

// Response wrappers
export interface ResultsWrapper<T> {
  results: T;
}

export interface PaginatedResultsWrapper<T> extends ResultsWrapper<T> {
  totalEntries: number;
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
  documentId: string;
  userId: string;
  collectionIds: string[];
  text: string;
  metadata: Record<string, any>;
  vector?: any;
}

// Collection types
export interface CollectionResponse {
  id: string;
  ownerId?: string;
  name: string;
  description?: string;
  graphClusterStatus: string;
  graphSyncStatus: string;
  createdAt: string;
  updatedAt: string;
  userCount: number;
  documentCount: number;
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
  createdAt: string;
  userId?: string;
  name?: string;
}

export interface Message {
  role: string;
  content: any;
  name?: string;
  functionCall?: Record<string, any>;
  toolCalls?: Array<Record<string, any>>;
  toolCallId?: string;
  metadata?: Record<string, any>;
}

export interface MessageResponse {
  id: string;
  message: any;
  metadata: Record<string, any>;
}
// Document types
export interface DocumentResponse {
  id: string;
  collectionIds: string[];
  ownerId: string;
  documentType: string;
  metadata: Record<string, any>;
  title?: string;
  version: string;
  sizeInBytes?: number;
  ingestionStatus: string;
  extractionStatus: string;
  createdAt: string;
  updatedAt: string;
  ingestionAttemptNumber?: number;
  summary?: string;
  summaryEmbedding?: string;
}

// Entity types
export interface EntityResponse {
  id: string;
  name: string;
  description?: string;
  category?: string;
  metadata: Record<string, any>;
  parentId?: string;
  chunkIds?: string[];
  descriptionEmbedding?: string;
}

// Graph types
export interface GraphResponse {
  id: string;
  userId: string;
  name: string;
  description: string;
  status: string;
  createdAt: string;
  updatedAt: string;
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
  taskId?: string;
  documentId: string;
}

export interface UpdateResponse {
  message: string;
  taskId?: string;
  documentId: string;
}

export interface IndexConfig {
  name?: string;
  tableName?: string;
  indexMethod?: string;
  indexMeasure?: string;
  indexArguments?: string;
  indexName?: string;
  indexColumn?: string;
  concurrently?: boolean;
}

// Prompt types
export interface PromptResponse {
  id: string;
  name: string;
  template: string;
  createdAt: string;
  updatedAt: string;
  inputTypes: string[];
}

// Relationship types
export interface RelationshipResponse {
  id: string;
  subject: string;
  predicate: string;
  object: string;
  description?: string;
  subjectId: string;
  objectId: string;
  weight: number;
  chunkIds: string[];
  parentId: string;
  metadata: Record<string, any>;
}

// Retrieval types
export interface ChunkSearchSettings {
  indexMeasure?: IndexMeasure;
  probes?: number;
  efSearch?: number;
  enabled?: boolean;
}

export interface GenerationConfig {
  model?: string;
  temperature?: number;
  topP?: number;
  maxTokensToSample?: number;
  stream?: boolean;
  functions?: Array<Record<string, any>>;
  tools?: Array<Record<string, any>>;
  addGenerationKwargs?: Record<string, any>;
  apiBase?: string;
  responseFormat?: Record<string, any> | object;
  extendedThinking?: boolean;
  thinkingBudget?: number;
  reasoningEffort?: string;
}

export interface HybridSearchSettings {
  fullTextWeight?: number;
  semanticWeight?: number;
  fullTextLimit?: number;
  rrfK?: number;
}

export interface GraphSearchSettings {
  generationConfig?: GenerationConfig;
  graphragMapSystem?: string;
  graphragReduceSystem?: string;
  maxCommunityDescriptionLength?: number;
  maxLlmQueriesForGlobalSearch?: number;
  limits?: Record<string, any>;
  enabled?: boolean;
}

export interface SearchSettings {
  useHybridSearch?: boolean;
  useSemanticSearch?: boolean;
  useFullTextSearch?: boolean;
  filters?: Record<string, any>;
  limit?: number;
  offset?: number;
  includeMetadata?: boolean;
  includeScores?: boolean;
  searchStrategy?: string;
  hybridSettings?: HybridSearchSettings;
  chunkSettings?: ChunkSearchSettings;
  graphSettings?: GraphSearchSettings;
}

export interface VectorSearchResult {
  chunkId: string;
  documentId: string;
  userId: string;
  collectionIds: string[];
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
  resultType?: KGSearchResultType;
  chunkIds?: string[];
  metadata: Record<string, any>;
  score?: number;
}

export interface CombinedSearchResponse {
  chunkSearchResults: VectorSearchResult[];
  graphSearchResults?: GraphSearchResult[];
}

// System types

export interface ServerStats {
  startTime: string;
  uptimeSeconds: number;
  cpuUsage: number;
  memoryUsage: number;
}

export interface SettingsResponse {
  config: Record<string, any>;
  prompts: Record<string, any>;
  r2rProjectName: string;
}

// User types

export type TokenType = "access" | "refresh";

export interface Token {
  token: string;
  tokenType: TokenType;
}

export interface TokenResponse {
  accessToken: Token;
  refreshToken: Token;
}

export interface User {
  id: string;
  email: string;
  isActive: boolean;
  isSuperuser: boolean;
  createdAt: string;
  updatedAt: string;
  isVerified: boolean;
  collectionIds: string[];
  hashedPassword?: string;
  verificationCodeExpiry?: string;
  name?: string;
  bio?: string;
  profilePicture?: string;
  metadata?: Record<string, any>;
  limitOverrides?: Record<string, any>;
  documentIds?: string[];
}

interface LoginResponse {
  accessToken: Token;
  refreshToken: Token;
}

interface StorageTypeLimit {
  limit: number;
  used: number;
  remaining: number;
}

interface StorageLimits {
  chunks: StorageTypeLimit;
  documents: StorageTypeLimit;
  collections: StorageTypeLimit;
}

interface UsageLimit {
  used: number;
  limit: number;
  remaining: number;
}

interface RouteUsage {
  routePerMin: UsageLimit;
  monthlyLimit: UsageLimit;
}

interface Usage {
  globalPerMin: UsageLimit;
  monthlyLimit: UsageLimit;
  routes: Record<string, RouteUsage>;
}

interface SystemDefaults {
  globalPerMin: number;
  routePerMin?: number;
  monthlyLimit: number;
}

interface LimitsResponse {
  storageLimits: StorageLimits;
  systemDefaults: SystemDefaults;
  userOverrides: Record<string, any>;
  effectiveLimits: SystemDefaults;
  usage: Usage;
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
export type WrappedVectorIndicesResponse = ResultsWrapper<IndexConfig[]>;

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
export type WrappedLimitsResponse = ResultsWrapper<LimitsResponse>;
export type WrappedLoginResponse = ResultsWrapper<LoginResponse>;

/**
 * The "base" shape for an R2R results wrapper.
 */
export interface R2RResults<T> {
  results: T;
  // Potentially other fields, e.g. "info", "status", etc.
}

/**
 * A paginated results wrapper typically includes a 'meta' object
 * or something similar for "total_entries".
 */
export interface PaginatedR2RResult<T> extends R2RResults<T> {
  meta: {
    total_entries: number;
  };
}

// ---------------------------
//  API Key Models
// ---------------------------

/**
 * Full API Key model (includes the private `api_key` which is only
 * returned ONCE at creation time).
 */
export interface ApiKey {
  public_key: string;
  /** The private key, only returned during creation. */
  api_key: string;
  key_id: string;
  name?: string;
}

/**
 * API Key model that omits the private `api_key`. Typically used
 * for listing user keys.
 */
export interface ApiKeyNoPriv {
  public_key: string;
  key_id: string;
  name?: string;
  updated_at: string; // or `Date` if your code auto-parses
}

/**
 * Wrapped response that contains one newly created API key.
 */
export type WrappedAPIKeyResponse = R2RResults<ApiKey>;

/**
 * Wrapped response that contains a list of existing API keys (no private keys).
 */
export type WrappedAPIKeysResponse = PaginatedR2RResult<ApiKeyNoPriv[]>;
