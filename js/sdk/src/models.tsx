export interface TokenInfo {
  token: string;
  tokenType: string;
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
  topP?: number;
  maxTokensToSample?: number;
  stream?: boolean;
  functions?: Array<Record<string, any>>;
  tools?: Array<Record<string, any>>;
  addGenerationKwargs?: Record<string, any>;
  apiBase?: string;
  responseFormat?: string;
}

export interface HybridSearchSettings {
  fullTextWeight: number;
  semanticWeight: number;
  fullTextLimit: number;
  rrfK: number;
}

export interface VectorSearchSettings {
  useVectorSearch?: boolean;
  useHybridSearch?: boolean;
  filters?: Record<string, any>;
  searchLimit?: number;
  offset?: number;
  selectedCollectionIds?: string[];
  indexMeasure: IndexMeasure;
  includeValues?: boolean;
  includeMetadatas?: boolean;
  probes?: number;
  efSearch?: number;
  hybridSearchSettings?: HybridSearchSettings;
  searchStrategy?: string;
}

export interface KGSearchSettings {
  useKgSearch?: boolean;
  filters?: Record<string, any>;
  selectedCollectionIds?: string[];
  graphragMapSystemPrompt?: string;
  kgSearchType?: "local";
  kgSearchLevel?: number | null;
  generationConfig?: GenerationConfig;
  // entityTypes?: any[];
  // relationships?: any[];
  maxCommunityDescriptionLength?: number;
  maxLlmQueriesForGlobalSearch?: number;
  localSearchLimits?: Record<string, number>;
}

export enum KGRunType {
  ESTIMATE = "estimate",
  RUN = "run",
}

export interface KGCreationSettings {
  kgRelationshipsExtractionPrompt?: string;
  kgEntityDescriptionPrompt?: string;
  forceKgCreation?: boolean;
  entityTypes?: string[];
  relationTypes?: string[];
  extractionsMergeCount?: number;
  maxKnowledgeRelationships?: number;
  maxDescriptionInputLength?: number;
  generationConfig?: GenerationConfig;
}

export interface KGEnrichmentSettings {
  forceKgEnrichment?: boolean;
  communityReportsPrompt?: string;
  maxSummaryInputLength?: number;
  generationConfig?: GenerationConfig;
  leidenParams?: Record<string, any>;
}

export interface KGEntityDeduplicationSettings {
  kgEntityDeduplicationType?: KGEntityDeduplicationType;
}

export enum KGEntityDeduplicationType {
  BY_NAME = "by_name",
  BY_DESCRIPTION = "by_description",
}

export interface KGLocalSearchResult {
  query: string;
  entities: Record<string, any>;
  relationships: Record<string, any>;
  communities: Record<string, any>;
}

export interface KGGlobalSearchResult {
  query: string;
  searchResult: string[];
}

export interface KGSearchResult {
  localResult?: KGLocalSearchResult;
  globalResult?: KGGlobalSearchResult;
}

export interface Message {
  role: string;
  content: string;
}

export interface R2RDocumentChunksRequest {
  documentId: string;
}

export enum IndexMeasure {
  COSINE_DISTANCE = "cosine_distance",
  L2_DISTANCE = "l2_distance",
  MAX_INNER_PRODUCT = "max_inner_product",
}

export interface RawChunk {
  text: string;
}
