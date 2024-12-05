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

export enum KGRunType {
  ESTIMATE = "estimate",
  RUN = "run",
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

export interface Message {
  role: string;
  content: string;
}

export interface R2RDocumentChunksRequest {
  documentId: string;
}

export interface RawChunk {
  text: string;
}
