export interface UnprocessedChunk {
  id: string;
  document_id?: string;
  collection_ids: string[];
  metadata: Record<string, any>;
  text: string;
}

// Shared wrappers
export interface ResultsWrapper<T> {
  results: T;
}

export interface PaginatedResultsWrapper<T> extends ResultsWrapper<T> {
  total_entries: number;
}

// Collection types
export interface CollectionResponse {
  collection_id: string;
  user_id?: string;
  name: string;
  description?: string;
  created_at: string;
  updated_at: string;
  user_count: number;
  document_count: number;
}

export type WrappedCollectionResponse = ResultsWrapper<CollectionResponse>;
export type WrappedCollectionsResponse = PaginatedResultsWrapper<
  CollectionResponse[]
>;

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

export type WrappedUserResponse = ResultsWrapper<UserResponse>;
export type WrappedUsersResponse = PaginatedResultsWrapper<UserResponse[]>;
