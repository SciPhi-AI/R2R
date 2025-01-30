import { r2rClient } from "../../r2rClient";
import {
  WrappedGraphResponse,
  WrappedBooleanResponse,
  WrappedGraphsResponse,
  WrappedEntityResponse,
  WrappedEntitiesResponse,
  WrappedRelationshipsResponse,
  WrappedRelationshipResponse,
  WrappedCommunitiesResponse,
  WrappedCommunityResponse,
} from "../../types";
import { downloadBlob } from "../../utils";

let fs: any;
if (typeof window === "undefined") {
  fs = require("fs");
}

export class GraphsClient {
  constructor(private client: r2rClient) {}

  /**
   * List graphs with pagination and filtering options.
   * @param collectionIds Optional list of collection IDs to filter by
   * @param offset Optional offset for pagination
   * @param limit Optional limit for pagination
   * @returns
   */
  async list(options?: {
    collectionIds?: string[];
    offset?: number;
    limit?: number;
  }): Promise<WrappedGraphsResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.collectionIds && options.collectionIds.length > 0) {
      params.collectionIds = options.collectionIds;
    }

    return this.client.makeRequest("GET", "graphs", {
      params,
    });
  }

  /**
   * Get detailed information about a specific graph.
   * @param collectionId The collection ID corresponding to the graph
   * @returns
   */
  async retrieve(options: {
    collectionId: string;
  }): Promise<WrappedGraphResponse> {
    return this.client.makeRequest("GET", `graphs/${options.collectionId}`);
  }

  /**
   * Deletes a graph and all its associated data.
   *
   * This endpoint permanently removes the specified graph along with all
   * entities and relationships that belong to only this graph.
   *
   * Entities and relationships extracted from documents are not deleted.
   * @param collectionId The collection ID corresponding to the graph
   * @returns
   */
  async reset(options: {
    collectionId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/reset`,
    );
  }

  /**
   * Update an existing graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param name Optional new name for the graph
   * @param description Optional new description for the graph
   * @returns
   */
  async update(options: {
    collectionId: string;
    name?: string;
    description?: string;
  }): Promise<WrappedGraphResponse> {
    const data = {
      ...(options.name && { name: options.name }),
      ...(options.description && { description: options.description }),
    };

    return this.client.makeRequest("POST", `graphs/${options.collectionId}`, {
      data,
    });
  }

  /**
   * Creates a new entity in the graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param entity Entity to add
   * @returns
   */
  async createEntity(options: {
    collectionId: string;
    name: string;
    description?: string;
    category?: string;
    metadata?: Record<string, any>;
  }): Promise<WrappedEntityResponse> {
    const data = {
      name: options.name,
      ...(options.description && { description: options.description }),
      ...(options.category && { category: options.category }),
      ...(options.metadata && { metadata: options.metadata }),
    };

    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/entities`,
      {
        data,
      },
    );
  }

  /**
   * List all entities in a graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listEntities(options: {
    collectionId: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedEntitiesResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest(
      "GET",
      `graphs/${options.collectionId}/entities`,
      {
        params,
      },
    );
  }

  /**
   * Retrieve an entity from a graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param entityId Entity ID to retrieve
   * @returns
   */
  async getEntity(options: {
    collectionId: string;
    entityId: string;
  }): Promise<WrappedEntityResponse> {
    return this.client.makeRequest(
      "GET",
      `graphs/${options.collectionId}/entities/${options.entityId}`,
    );
  }

  /**
   * Updates an existing entity in the graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param entityId Entity ID to update
   * @param entity Entity to update
   * @returns
   */
  async updateEntity(options: {
    collectionId: string;
    entityId: string;
    name?: string;
    description?: string;
    category?: string;
    metadata?: Record<string, any>;
  }): Promise<WrappedEntityResponse> {
    const data = {
      ...(options.name && { name: options.name }),
      ...(options.description && { description: options.description }),
      ...(options.category && { category: options.category }),
      ...(options.metadata && { metadata: options.metadata }),
    };

    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/entities/${options.entityId}`,
      {
        data,
      },
    );
  }

  /**
   * Remove an entity from a graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param entityId Entity ID to remove
   * @returns
   */
  async removeEntity(options: {
    collectionId: string;
    entityId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `graphs/${options.collectionId}/entities/${options.entityId}`,
    );
  }
  /**
   * Creates a new relationship in the graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param relationship Relationship to add
   * @returns
   */
  async createRelationship(options: {
    collectionId: string;
    subject: string;
    subjectId: string;
    predicate: string;
    object: string;
    objectId: string;
    description: string;
    weight?: number;
    metadata?: Record<string, any>;
  }): Promise<WrappedRelationshipResponse> {
    const data = {
      subject: options.subject,
      subject_id: options.subjectId,
      predicate: options.predicate,
      object: options.object,
      object_id: options.objectId,
      description: options.description,
      ...(options.weight && { weight: options.weight }),
      ...(options.metadata && { metadata: options.metadata }),
    };

    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/relationships`,
      {
        data,
      },
    );
  }

  /**
   * List all relationships in a graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listRelationships(options: {
    collectionId: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedRelationshipsResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest(
      "GET",
      `graphs/${options.collectionId}/relationships`,
      {
        params,
      },
    );
  }

  /**
   * Retrieve a relationship from a graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param relationshipId Relationship ID to retrieve
   * @returns
   */
  async getRelationship(options: {
    collectionId: string;
    relationshipId: string;
  }): Promise<WrappedRelationshipResponse> {
    return this.client.makeRequest(
      "GET",
      `graphs/${options.collectionId}/relationships/${options.relationshipId}`,
    );
  }

  /**
   * Updates an existing relationship in the graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param relationshipId Relationship ID to update
   * @param relationship Relationship to update
   * @returns WrappedRelationshipResponse
   */
  async updateRelationship(options: {
    collectionId: string;
    relationshipId: string;
    subject?: string;
    subjectId?: string;
    predicate?: string;
    object?: string;
    objectId?: string;
    description?: string;
    weight?: number;
    metadata?: Record<string, any>;
  }): Promise<WrappedRelationshipResponse> {
    const data = {
      ...(options.subject && { subject: options.subject }),
      ...(options.subjectId && { subject_id: options.subjectId }),
      ...(options.predicate && { predicate: options.predicate }),
      ...(options.object && { object: options.object }),
      ...(options.objectId && { object_id: options.objectId }),
      ...(options.description && { description: options.description }),
      ...(options.weight && { weight: options.weight }),
      ...(options.metadata && { metadata: options.metadata }),
    };

    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/relationships/${options.relationshipId}`,
      {
        data,
      },
    );
  }

  /**
   * Remove a relationship from a graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param relationshipId Entity ID to remove
   * @returns
   */
  async removeRelationship(options: {
    collectionId: string;
    relationshipId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `graphs/${options.collectionId}/relationships/${options.relationshipId}`,
    );
  }

  /**
   * Export graph entities as a CSV file with support for filtering and column selection.
   *
   * @param options Export configuration options
   * @param options.outputPath Path where the CSV file should be saved (Node.js only)
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which documents are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   * @returns Promise<Blob> in browser environments, Promise<void> in Node.js
   */
  async exportEntities(options: {
    collectionId: string;
    outputPath?: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<Blob | void> {
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
      `graphs/${options.collectionId}/entities/export`,
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
   * Export graph entities as a CSV file and save it to the user's device.
   * @param filename
   * @param options
   */
  async exportEntitiesToFile(options: {
    filename: string;
    collectionId: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<void> {
    const blob = await this.exportEntities(options);
    if (blob instanceof Blob) {
      downloadBlob(blob, options.filename);
    }
  }

  /**
   * Export graph relationships as a CSV file with support for filtering and column selection.
   *
   * @param options Export configuration options
   * @param options.outputPath Path where the CSV file should be saved (Node.js only)
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which documents are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   * @returns Promise<Blob> in browser environments, Promise<void> in Node.js
   */
  async exportRelationships(options: {
    collectionId: string;
    outputPath?: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<Blob | void> {
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
      `graphs/${options.collectionId}/relationships/export`,
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
   * Export graph relationships as a CSV file and save it to the user's device.
   * @param filename
   * @param options
   */
  async exportRelationshipsToFile(options: {
    filename: string;
    collectionId: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<void> {
    const blob = await this.exportRelationships(options);
    if (blob instanceof Blob) {
      downloadBlob(blob, options.filename);
    }
  }

  /**
   * Export graph communities as a CSV file with support for filtering and column selection.
   *
   * @param options Export configuration options
   * @param options.outputPath Path where the CSV file should be saved (Node.js only)
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which documents are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   * @returns Promise<Blob> in browser environments, Promise<void> in Node.js
   */
  async exportCommunities(options: {
    collectionId: string;
    outputPath?: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<Blob | void> {
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
      `graphs/${options.collectionId}/communities/export`,
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
   * Export graph communities as a CSV file and save it to the user's device.
   * @param filename
   * @param options
   */
  async exportCommunitiesToFile(options: {
    filename: string;
    collectionId: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<void> {
    const blob = await this.exportRelationships(options);
    if (blob instanceof Blob) {
      downloadBlob(blob, options.filename);
    }
  }

  /**
   * Creates a new community in the graph.
   *
   * While communities are typically built automatically via the /graphs/{id}/communities/build endpoint,
   * this endpoint allows you to manually create your own communities.
   *
   * This can be useful when you want to:
   *  - Define custom groupings of entities based on domain knowledge
   *  - Add communities that weren't detected by the automatic process
   *  - Create hierarchical organization structures
   *  - Tag groups of entities with specific metadata
   *
   * The created communities will be integrated with any existing automatically detected communities
   * in the graph's community structure.
   *
   * @param collectionId The collection ID corresponding to the graph
   * @param name Name of the community
   * @param summary Summary of the community
   * @param findings Findings or insights about the community
   * @param rating Rating of the community
   * @param ratingExplanation Explanation of the community rating
   * @param attributes Additional attributes to associate with the community
   * @returns WrappedCommunityResponse
   */
  async createCommunity(options: {
    collectionId: string;
    name: string;
    summary: string;
    findings?: string[];
    rating?: number;
    ratingExplanation?: string;
    attributes?: Record<string, any>;
  }): Promise<WrappedCommunityResponse> {
    const data = {
      name: options.name,
      ...(options.summary && { summary: options.summary }),
      ...(options.findings && { findings: options.findings }),
      ...(options.rating && { rating: options.rating }),
      ...(options.ratingExplanation && {
        rating_explanation: options.ratingExplanation,
      }),
      ...(options.attributes && { attributes: options.attributes }),
    };

    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/communities`,
      {
        data,
      },
    );
  }

  /**
   * List all communities in a graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listCommunities(options: {
    collectionId: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedCommunitiesResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    return this.client.makeRequest(
      "GET",
      `graphs/${options.collectionId}/communities`,
      {
        params,
      },
    );
  }

  /**
   * Retrieve a community from a graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param communityId Entity ID to retrieve
   * @returns
   */
  async getCommunity(options: {
    collectionId: string;
    communityId: string;
  }): Promise<WrappedCommunityResponse> {
    return this.client.makeRequest(
      "GET",
      `graphs/${options.collectionId}/communities/${options.communityId}`,
    );
  }

  /**
   * Updates an existing community in the graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param communityId Community ID to update
   * @param entity Entity to update
   * @returns WrappedCommunityResponse
   */
  async updateCommunity(options: {
    collectionId: string;
    communityId: string;
    name?: string;
    summary?: string;
    findings?: string[];
    rating?: number;
    ratingExplanation?: string;
    attributes?: Record<string, any>;
  }): Promise<WrappedCommunityResponse> {
    const data = {
      ...(options.name && { name: options.name }),
      ...(options.summary && { summary: options.summary }),
      ...(options.findings && { findings: options.findings }),
      ...(options.rating && { rating: options.rating }),
      ...(options.ratingExplanation && {
        rating_explanation: options.ratingExplanation,
      }),
      ...(options.attributes && { attributes: options.attributes }),
    };
    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/communities/${options.communityId}`,
      {
        data,
      },
    );
  }

  /**
   * Delete a community in a graph.
   * @param collectionId The collection ID corresponding to the graph
   * @param communityId Community ID to delete
   * @returns
   */
  async deleteCommunity(options: {
    collectionId: string;
    communityId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `graphs/${options.collectionId}/communities/${options.communityId}`,
    );
  }

  /**
   * Adds documents to a graph by copying their entities and relationships.
   *
   * This endpoint:
   *  1. Copies document entities to the graphs_entities table
   *  2. Copies document relationships to the graphs_relationships table
   *  3. Associates the documents with the graph
   *
   * When a document is added:
   *  - Its entities and relationships are copied to graph-specific tables
   *  - Existing entities/relationships are updated by merging their properties
   *  - The document ID is recorded in the graph's document_ids array
   *
   * Documents added to a graph will contribute their knowledge to:
   *  - Graph analysis and querying
   *  - Community detection
   *  - Knowledge graph enrichment
   *
   * The user must have access to both the graph and the documents being added.
   * @param collectionId The collection ID corresponding to the graph
   * @returns
   */
  async pull(options: {
    collectionId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/pull`,
    );
  }

  /**
   * Removes a document from a graph and removes any associated entities
   *
   * This endpoint:
   *  1. Removes the document ID from the graph's document_ids array
   *  2. Optionally deletes the document's copied entities and relationships
   *
   * The user must have access to both the graph and the document being removed.
   * @param collectionId The collection ID corresponding to the graph
   * @param documentId The document ID to remove
   * @returns
   */
  async removeDocument(options: {
    collectionId: string;
    documentId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `graphs/${options.collectionId}/documents/${options.documentId}`,
    );
  }

  /**
   * Creates communities in the graph by analyzing entity relationships and similarities.
   *
   * Communities are created through the following process:
   * 1. Analyzes entity relationships and metadata to build a similarity graph
   * 2. Applies advanced community detection algorithms (e.g. Leiden) to identify densely connected groups
   * 3. Creates hierarchical community structure with multiple granularity levels
   * 4. Generates natural language summaries and statistical insights for each community
   *
   * The resulting communities can be used to:
   * - Understand high-level graph structure and organization
   * - Identify key entity groupings and their relationships
   * - Navigate and explore the graph at different levels of detail
   * - Generate insights about entity clusters and their characteristics
   *
   * The community detection process is configurable through settings like:
   * - Community detection algorithm parameters
   * - Summary generation prompt
   *
   * @param options
   * @returns
   */
  async buildCommunities(options: {
    collectionId: string;
    runType?: string;
    kgEntichmentSettings?: Record<string, any>;
    runWithOrchestration?: boolean;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/communities/build`,
    );
  }
}
