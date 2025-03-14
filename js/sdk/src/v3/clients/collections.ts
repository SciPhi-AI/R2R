import { r2rClient } from "../../r2rClient";
import {
  WrappedBooleanResponse,
  WrappedGenericMessageResponse,
  WrappedCollectionResponse,
  WrappedCollectionsResponse,
  WrappedDocumentsResponse,
  WrappedUsersResponse,
} from "../../types";
import { downloadBlob } from "../../utils";

let fs: any;
if (typeof window === "undefined") {
  fs = require("fs");
}

export class CollectionsClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new collection.
   * @param name Name of the collection
   * @param description Optional description of the collection
   * @returns A promise that resolves with the created collection
   */
  async create(options: {
    name: string;
    description?: string;
  }): Promise<WrappedCollectionResponse> {
    return this.client.makeRequest("POST", "collections", {
      data: options,
    });
  }

  /**
   * List collections with pagination and filtering options.
   * @param ids Optional list of collection IDs to filter by
   * @param offset Optional offset for pagination
   * @param limit Optional limit for pagination
   * @returns
   */
  async list(options?: {
    ids?: string[];
    offset?: number;
    limit?: number;
  }): Promise<WrappedCollectionsResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.ids && options.ids.length > 0) {
      params.ids = options.ids;
    }

    return this.client.makeRequest("GET", "collections", {
      params,
    });
  }

  /**
   * Get detailed information about a specific collection.
   * @param id Collection ID to retrieve
   * @returns
   */
  async retrieve(options: { id: string }): Promise<WrappedCollectionResponse> {
    return this.client.makeRequest("GET", `collections/${options.id}`);
  }

  /**
   * Update an existing collection.
   * @param id Collection ID to update
   * @param name Optional new name for the collection
   * @param description Optional new description for the collection
   * @param generateDescription Whether to generate a new synthetic description for the collection
   * @returns
   */
  async update(options: {
    id: string;
    name?: string;
    description?: string;
    generateDescription?: boolean;
  }): Promise<WrappedCollectionResponse> {
    const data = {
      ...(options.name && { name: options.name }),
      ...(options.description && { description: options.description }),
      ...(options.generateDescription !== undefined && {
        generate_description: options.generateDescription,
      }),
    };

    return this.client.makeRequest("POST", `collections/${options.id}`, {
      data,
    });
  }

  /**
   * Delete a collection.
   * @param id Collection ID to delete
   * @returns
   */
  async delete(options: { id: string }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `collections/${options.id}`);
  }

  /**
   * List all documents in a collection.
   * @param id Collection ID
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listDocuments(options: {
    id: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedDocumentsResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest(
      "GET",
      `collections/${options.id}/documents`,
      {
        params,
      },
    );
  }

  /**
   * Add a document to a collection.
   * @param id Collection ID
   * @param documentId Document ID to add
   * @returns
   */
  async addDocument(options: {
    id: string;
    documentId: string;
  }): Promise<WrappedGenericMessageResponse> {
    return this.client.makeRequest(
      "POST",
      `collections/${options.id}/documents/${options.documentId}`,
    );
  }

  /**
   * Remove a document from a collection.
   * @param id Collection ID
   * @param documentId Document ID to remove
   * @returns
   */
  async removeDocument(options: {
    id: string;
    documentId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `collections/${options.id}/documents/${options.documentId}`,
    );
  }

  /**
   * List all users in a collection.
   * @param id Collection ID
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listUsers(options: {
    id: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedUsersResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest("GET", `collections/${options.id}/users`, {
      params,
    });
  }

  /**
   * Add a user to a collection.
   * @param id Collection ID
   * @param userId User ID to add
   * @returns
   */
  async addUser(options: {
    id: string;
    userId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "POST",
      `collections/${options.id}/users/${options.userId}`,
    );
  }

  /**
   * Remove a user from a collection.
   * @param id Collection ID
   * @param userId User ID to remove
   * @returns
   */
  async removeUser(options: {
    id: string;
    userId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `collections/${options.id}/users/${options.userId}`,
    );
  }

  /**
   * Creates communities in the graph by analyzing entity relationships and similarities.
   *
   * Communities are created through the following process:
   *  1. Analyzes entity relationships and metadata to build a similarity graph
   *  2. Applies advanced community detection algorithms (e.g. Leiden) to identify densely connected groups
   *  3. Creates hierarchical community structure with multiple granularity levels
   *  4. Generates natural language summaries and statistical insights for each community
   *
   * The resulting communities can be used to:
   *  - Understand high-level graph structure and organization
   *  - Identify key entity groupings and their relationships
   *  - Navigate and explore the graph at different levels of detail
   *  - Generate insights about entity clusters and their characteristics
   *
   * The community detection process is configurable through settings like:
   *  - Community detection algorithm parameters
   *  - Summary generation prompt
   * @param collectionId The collection ID corresponding to the graph
   * @returns
   */
  async extract(options: {
    collectionId: string;
    settings?: Record<string, any>;
    runWithOrchestration?: boolean;
  }): Promise<WrappedBooleanResponse> {
    const data = {
      ...(options.settings && { settings: options.settings }),
      ...(options.runWithOrchestration !== undefined && {
        run_with_orchestration: options.runWithOrchestration,
      }),
    };

    return this.client.makeRequest(
      "POST",
      `collections/${options.collectionId}/extract`,
      {
        data,
      },
    );
  }

  /**
   * Export collections as a CSV file with support for filtering and column selection.
   *
   * @param options Export configuration options
   * @param options.outputPath Path where the CSV file should be saved (Node.js only)
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which collections are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   * @returns Promise<Blob> in browser environments, Promise<void> in Node.js
   */
  async export(
    options: {
      outputPath?: string;
      columns?: string[];
      filters?: Record<string, any>;
      includeHeader?: boolean;
    } = {},
  ): Promise<Blob | void> {
    const data: Record<string, any> = {
      include_header: options.includeHeader ?? true,
    };

    if (options.columns) {
      data.columns = options.columns;
    }
    if (options.filters) {
      data.filters = options.filters;
    }

    const response = await this.client.makeRequest(
      "POST",
      "collections/export",
      {
        data,
        responseType: "arraybuffer",
        headers: { Accept: "text/csv" },
      },
    );

    // Node environment
    if (options.outputPath && typeof process !== "undefined") {
      await fs.promises.writeFile(options.outputPath, Buffer.from(response));
      return;
    }

    // Browser
    return new Blob([response], { type: "text/csv" });
  }

  /**
   * Export collections as a CSV file and save it to the user's device.
   * @param filename
   * @param options
   */
  async exportToFile(options: {
    filename: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<void> {
    const blob = await this.export(options);
    if (blob instanceof Blob) {
      downloadBlob(blob, options.filename);
    }
  }

  /**
   * Retrieve a collection by its name.
   * @param name The name of the collection to retrieve.
   * @returns A promise that resolves with the collection details.
   */
  async retrieveByName(options: {
    name: string;
    ownerId?: string;
  }): Promise<WrappedCollectionResponse> {
    const queryParams: Record<string, any> = {};
    if (options.ownerId) {
      queryParams.owner_id = options.ownerId;
    }
    return this.client.makeRequest("GET", `collections/name/${options.name}`, {
      params: queryParams,
    });
  }
}
