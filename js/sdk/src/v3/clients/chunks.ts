import { r2rClient } from "../../r2rClient";
import { UnprocessedChunk } from "../../types";

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
     * @param run_with_orchestration Optional flag to run with orchestration
     * @returns
     */
  async create(options: {
    chunks: UnprocessedChunk[];
    run_with_orchestration?: boolean;
  }): Promise<any> {
    return this.client.makeRequest("POST", "chunks", {
      data: {
        raw_chunks: options.chunks,
        run_with_orchestration: options.run_with_orchestration,
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
  }): Promise<any> {
    return this.client.makeRequest("POST", `chunks/${options.id}`, {
      data: options,
    });
  }

  /**
   * Get a specific chunk.
   * @param id ID of the chunk to retrieve
   * @returns
   */
  async retrieve(options: { id: string }): Promise<any> {
    return this.client.makeRequest("GET", `chunks/${options.id}`);
  }

  /**
   * Delete a specific chunk.
   * @param id ID of the chunk to delete
   * @returns
   */
  async delete(id: string): Promise<any> {
    return this.client.makeRequest("DELETE", `chunks/${id}`);
  }

  /**
   * List chunks.
   * @param include_vectors Include vector data in response. Defaults to False.
   * @param metadata_filters Filter by metadata. Defaults to None.
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async list(options?: {
    include_vectors?: boolean;
    metadata_filters?: Record<string, any>;
    offset?: number;
    limit?: number;
  }): Promise<any> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.include_vectors) {
      params.include_vectors = options.include_vectors;
    }

    if (options?.metadata_filters) {
      params.metadata_filters = options.metadata_filters;
    }

    return this.client.makeRequest("GET", "chunks", {
      params,
    });
  }
}
