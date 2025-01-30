import { r2rClient } from "../../r2rClient";
import {
  UnprocessedChunk,
  WrappedBooleanResponse,
  WrappedChunkResponse,
  WrappedChunksResponse,
} from "../../types";
import { ensureSnakeCase } from "../../utils";

export class ChunksClient {
  constructor(private client: r2rClient) {}

  /**
   * Create multiple chunks.
   * @param chunks List of UnprocessedChunk objects containing:
              - id: Optional UUID
              - document_id: Optional UUID
              - collection_ids: list UUID
              - metadata: dict
              - text: string
    * @param runWithOrchestration Optional flag to run with orchestration
    * @returns
    */
  async create(options: {
    chunks: UnprocessedChunk[];
    runWithOrchestration?: boolean;
  }): Promise<any> {
    return this.client.makeRequest("POST", "chunks", {
      data: {
        raw_chunks: ensureSnakeCase(options.chunks),
        runWithOrchestration: options.runWithOrchestration,
      },
    });
  }

  /**
   * Update an existing chunk.
   * @param id ID of the chunk to update
   * @param text Optional new text for the chunk
   * @param metadata Optional new metadata for the chunk
   * @returns
   */
  async update(options: {
    id: string;
    text?: string;
    metadata?: any;
  }): Promise<WrappedChunkResponse> {
    return this.client.makeRequest("POST", `chunks/${options.id}`, {
      data: options,
    });
  }

  /**
   * Get a specific chunk.
   * @param id ID of the chunk to retrieve
   * @returns
   */
  async retrieve(options: { id: string }): Promise<WrappedChunkResponse> {
    return this.client.makeRequest("GET", `chunks/${options.id}`);
  }

  /**
   * Delete a specific chunk.
   * @param id ID of the chunk to delete
   * @returns
   */
  async delete(options: { id: string }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `chunks/${options.id}`);
  }

  /**
   * List chunks.
   * @param includeVectors Include vector data in response. Defaults to False.
   * @param metadataFilters Filter by metadata. Defaults to None.
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async list(options?: {
    includeVectors?: boolean;
    metadataFilters?: Record<string, any>;
    offset?: number;
    limit?: number;
  }): Promise<WrappedChunksResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.includeVectors) {
      params.include_vectors = options.includeVectors;
    }

    if (options?.metadataFilters) {
      params.metadata_filters = options.metadataFilters;
    }

    return this.client.makeRequest("GET", "chunks", {
      params,
    });
  }
}
