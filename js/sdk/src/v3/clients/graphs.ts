import { feature } from "../../feature";
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
  Entity,
  Relationship,
} from "../../types";

export class GraphsClient {
  constructor(private client: r2rClient) {}

  /**
   * List graphs with pagination and filtering options.
   * @param ids Optional list of graph IDs to filter by
   * @param offset Optional offset for pagination
   * @param limit Optional limit for pagination
   * @returns
   */
  @feature("graphs.list")
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
      params.ids = options.collectionIds;
    }

    return this.client.makeRequest("GET", "graphs", {
      params,
    });
  }

  /**
   * Get detailed information about a specific graph.
   * @param id Graph ID to retrieve
   * @returns
   */
  @feature("graphs.retrieve")
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
   * Entities and relationships extracted from documents are not deleted
   * and must be deleted separately using the /entities and /relationships
   * endpoints.
   * @param collectionId The collection ID of the graph to delete
   * @returns
   */
  @feature("graphs.reset")
  async reset(options: {
    collectionId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `graphs/${options.collectionId}`);
  }

  /**
   * Update an existing graph.
   * @param id Graph ID to update
   * @param name Optional new name for the graph
   * @param description Optional new description for the graph
   * @returns
   */
  @feature("graphs.update")
  async update(options: {
    id: string;
    name?: string;
    description?: string;
  }): Promise<WrappedGraphResponse> {
    const data = {
      ...(options.name && { name: options.name }),
      ...(options.description && { description: options.description }),
    };

    return this.client.makeRequest("POST", `graphs/${options.id}`, {
      data,
    });
  }

  /**
   * Creates a new entity in the graph.
   * @param collectionId The collection ID corresponding to the graph to add the entity to.
   * @param entity Entity to add
   * @returns
   */
  @feature("graphs.createEntity")
  async createEntity(options: {
    collectionId: string;
    entity: Entity;
  }): Promise<WrappedEntityResponse> {
    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/entities`,
      {
        data: options.entity,
      },
    );
  }

  /**
   * List all entities in a graph.
   * @param collectionId Collection ID
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  @feature("graphs.listEntities")
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
   * @param collectionId The collection ID corresponding to the graph to add the entity to.
   * @param entityId Entity ID to retrieve
   * @returns
   */
  @feature("graphs.getEntity")
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
   * @param collectionId The collection ID corresponding to the graph to add the entity to.
   * @param entityId Entity ID to update
   * @param entity Entity to update
   * @returns
   */
  @feature("graphs.updateEntity")
  async updateEntity(options: {
    collectionId: string;
    entityId: string;
    entity: Entity;
  }): Promise<WrappedEntityResponse> {
    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/entities/${options.entityId}`,
      {
        data: options.entity,
      },
    );
  }

  /**
   * Remove an entity from a graph.
   * @param collectionId The collection ID corresponding to the graph to add the entity to.
   * @param entityId Entity ID to remove
   * @returns
   */
  @feature("graphs.removeEntity")
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
   * @param collectionId The collection ID corresponding to the graph to add the entity to.
   * @param relationship Relationship to add
   * @returns
   */
  @feature("graphs.createRelationship")
  async createRelationship(options: {
    collectionId: string;
    relationship: Relationship;
  }): Promise<WrappedRelationshipResponse> {
    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/relationships`,
      {
        data: options.relationship,
      },
    );
  }

  /**
   * List all relationships in a graph.
   * @param collectionId Collection ID
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  @feature("graphs.listRelationships")
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
   * @param collectionId The collection ID corresponding to the graph to add the entity to.
   * @param relationshipId Relationship ID to retrieve
   * @returns
   */
  @feature("graphs.getRelationship")
  async getRelationship(options: {
    collectionId: string;
    relationshipId: string;
  }): Promise<WrappedRelationshipResponse> {
    return this.client.makeRequest(
      "GET",
      `graphs/${options.collectionId}/entities/${options.relationshipId}`,
    );
  }

  /**
   * Updates an existing relationship in the graph.
   * @param collectionId The collection ID corresponding to the graph to add the entity to.
   * @param relationshipId Relationship ID to update
   * @param relationship Relationship to update
   * @returns
   */
  @feature("graphs.updateRelationship")
  async updateRelationship(options: {
    collectionId: string;
    relationshipId: string;
    relationship: Relationship;
  }): Promise<WrappedRelationshipResponse> {
    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/relationships/${options.relationshipId}`,
      {
        data: options.relationship,
      },
    );
  }

  /**
   * Remove a relationship from a graph.
   * @param collectionId The collection ID corresponding to the graph to add the entity to.
   * @param relationshipId Entity ID to remove
   * @returns
   */
  @feature("graphs.removeRelationship")
  async removeRelationship(options: {
    collectionId: string;
    relationshipId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "DELETE",
      `graphs/${options.collectionId}/entities/${options.relationshipId}`,
    );
  }

  /**
   * List all communities in a graph.
   * @param collectionId Collection ID
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  @feature("graphs.listCommunities")
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
   * @param collectionId The ID of the collection to get communities for.
   * @param communityId Entity ID to retrieve
   * @returns
   */
  @feature("graphs.getCommunity")
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
   * @param collectionId The collection ID corresponding to the graph to add the entity to.
   * @param communityId Community ID to update
   * @param entity Entity to update
   * @returns WrappedEntityResponse
   */
  @feature("graphs.updateCommunity")
  async updateCommunity(options: {
    collectionId: string;
    communityId: string;
    name?: string;
    summary?: string;
    findings?: string[];
    rating?: number;
    ratingExplanation?: string;
    level?: number;
    attributes?: Record<string, any>;
  }): Promise<WrappedEntityResponse> {
    const data = {
      ...(options.name && { name: options.name }),
      ...(options.summary && { summary: options.summary }),
      ...(options.findings && { findings: options.findings }),
      ...(options.rating && { rating: options.rating }),
      ...(options.ratingExplanation && {
        rating_explanation: options.ratingExplanation,
      }),
      ...(options.level && { level: options.level }),
      ...(options.attributes && { attributes: options.attributes }),
    };
    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/entities/${options.communityId}`,
      {
        data,
      },
    );
  }

  /**
   * Adds documents to a graph by copying their entities and relationships.
   *
   * This endpoint:
   *  1. Copies document entities to the graph_entity table
   *  2. Copies document relationships to the graph_relationship table
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
   * @param options
   * @returns
   */
  @feature("graphs.pull")
  async pull(options: {
    collectionId: string;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest(
      "POST",
      `graphs/${options.collectionId}/pull`,
    );
  }
}
