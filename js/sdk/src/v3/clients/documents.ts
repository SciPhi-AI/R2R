import { r2rClient } from "../../r2rClient";
import FormData from "form-data";
import {
  WrappedBooleanResponse,
  WrappedChunksResponse,
  WrappedCollectionsResponse,
  WrappedDocumentResponse,
  WrappedDocumentsResponse,
  WrappedEntitiesResponse,
  WrappedIngestionResponse,
  WrappedRelationshipsResponse,
  WrappedGenericMessageResponse,
  WrappedDocumentSearchResponse,
} from "../../types";
import { downloadBlob } from "../../utils";
import { ensureSnakeCase } from "../../utils";

let fs: any;
if (typeof window === "undefined") {
  fs = require("fs");
}

import axios from "axios";
import * as os from "os";
import * as path from "path";
import { v5 as uuidv5 } from "uuid";

type FileInput = string | File | { path: string; name: string };

// Define SearchMode and SearchSettings types (can be more specific if needed)
export type SearchMode = "basic" | "advanced" | "custom";
export interface SearchSettings {
  // Define known settings based on Python/Router if possible
  limit?: number;
  filters?: Record<string, any>;
  useSemanticSearch?: boolean;
  useHybridSearch?: boolean;
  hybridSettings?: Record<string, any>;
  useGraphSearch?: boolean;
  graphSettings?: Record<string, any>;
  // Add other relevant settings
  [key: string]: any; // Allow flexible settings
}

export class DocumentsClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new document from either a file or content.
   *
   * Note: Access control might apply based on user limits (max documents, chunks, collections).
   *
   * @param file The file to upload, if any
   * @param raw_text Optional raw text content to upload, if no file path is provided
   * @param chunks Optional array of pre-processed text chunks to ingest
   * @param id Optional ID to assign to the document
   * @param collectionIds Collection IDs to associate with the document. If none are provided, the document will be assigned to the user's default collection.
   * @param metadata Optional metadata to assign to the document
   * @param ingestionConfig Optional ingestion configuration to use
   * @param runWithOrchestration Optional flag to run with orchestration (default: true)
   * @param ingestionMode Optional ingestion mode (default: 'custom')
   * @returns Promise<WrappedIngestionResponse>
   */
  async create(options: {
    file?: FileInput;
    raw_text?: string;
    chunks?: string[];
    id?: string;
    metadata?: Record<string, any>;
    ingestionConfig?: Record<string, any>;
    collectionIds?: string[];
    runWithOrchestration?: boolean;
    ingestionMode?: "hi-res" | "ocr" | "fast" | "custom";
  }): Promise<WrappedIngestionResponse> {
    const inputCount = [options.file, options.raw_text, options.chunks].filter(
      (x) => x !== undefined,
    ).length;
    if (inputCount === 0) {
      throw new Error("Either file, raw_text, or chunks must be provided");
    }
    if (inputCount > 1) {
      throw new Error("Only one of file, raw_text, or chunks may be provided");
    }

    const formData = new FormData();
    // Removed processedFiles array as file_names is not used by the router

    const processPath = async (path: FileInput): Promise<void> => {
      const appendFile = (
        file: File | NodeJS.ReadableStream,
        filename: string,
      ) => {
        formData.append(`file`, file, filename);
        // Removed pushing to processedFiles
      };

      if (typeof path === "string") {
        if (typeof window === "undefined") {
          const stat = await fs.promises.stat(path);
          if (stat.isDirectory()) {
            throw new Error("Directories are not supported in create()");
          } else {
            appendFile(fs.createReadStream(path), path.split("/").pop() || "");
          }
        } else {
          console.warn(
            "File path provided in browser environment. This is not supported. Use a File object instead.",
          );
          throw new Error(
            "File paths are not supported in the browser. Use a File object.",
          );
        }
      } else if (path instanceof File) {
        appendFile(path, path.name);
      } else if ("path" in path && "name" in path) {
        if (typeof window === "undefined") {
          appendFile(fs.createReadStream(path.path), path.name);
        } else {
          console.warn(
            "File path object provided in browser environment. This is not supported. Use a File object instead.",
          );
          throw new Error(
            "File path objects are not supported in the browser. Use a File object.",
          );
        }
      }
    };

    if (options.file) {
      await processPath(options.file);
    }

    if (options.raw_text) {
      formData.append("raw_text", options.raw_text);
    }
    if (options.chunks) {
      formData.append("chunks", JSON.stringify(options.chunks));
    }
    if (options.id) {
      formData.append("id", options.id);
    }
    if (options.metadata) {
      formData.append("metadata", JSON.stringify(options.metadata));
    }
    if (options.ingestionConfig) {
      formData.append(
        "ingestion_config",
        JSON.stringify(ensureSnakeCase(options.ingestionConfig)),
      );
    }
    if (options.collectionIds?.length) {
      formData.append("collection_ids", JSON.stringify(options.collectionIds));
    }
    if (options.runWithOrchestration !== undefined) {
      formData.append(
        "run_with_orchestration",
        String(options.runWithOrchestration),
      );
    }
    if (options.ingestionMode) {
      formData.append("ingestion_mode", options.ingestionMode);
    }

    return this.client.makeRequest("POST", "documents", {
      data: formData,
      headers: formData.getHeaders?.() ?? {
        "Content-Type": "multipart/form-data",
      },
      transformRequest: [
        (data: any, headers: Record<string, string>) => {
          return data;
        },
      ],
    });
  }

  /**
   * Append metadata to a document.
   *
   * Note: Users can typically only modify metadata for documents they own. Superusers may have broader access.
   *
   * @param id ID of document to append metadata to
   * @param metadata List of metadata entries (key-value pairs) to append
   * @returns Promise<WrappedDocumentResponse>
   */
  async appendMetadata(options: {
    id: string;
    metadata: Record<string, any>[];
  }): Promise<WrappedDocumentResponse> {
    return this.client.makeRequest(
      "PATCH",
      `documents/${options.id}/metadata`,
      {
        data: options.metadata,
      },
    );
  }

  /**
   * Replace metadata for a document. This overwrites all existing metadata.
   *
   * Note: Users can typically only replace metadata for documents they own. Superusers may have broader access.
   *
   * @param id ID of document to replace metadata for
   * @param metadata The new list of metadata entries (key-value pairs)
   * @returns Promise<WrappedDocumentResponse>
   */
  async replaceMetadata(options: {
    id: string;
    metadata: Record<string, any>[];
  }): Promise<WrappedDocumentResponse> {
    return this.client.makeRequest("PUT", `documents/${options.id}/metadata`, {
      data: options.metadata,
    });
  }

  /**
   * Get details for a specific document by ID.
   *
   * Note: Users can only retrieve documents they own or have access to through collections. Superusers can retrieve any document.
   *
   * @param id ID of document to retrieve
   * @returns Promise<WrappedDocumentResponse>
   */
  async retrieve(options: { id: string }): Promise<WrappedDocumentResponse> {
    return this.client.makeRequest("GET", `documents/${options.id}`);
  }

  /**
   * List documents with pagination.
   *
   * Note: Regular users will only see documents they own or have access to through collections. Superusers can see all documents.
   *
   * @param ids Optional list of document IDs to filter by
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 1000. Defaults to 100.
   * @param includeSummaryEmbeddings Specifies whether or not to include embeddings of each document summary. Defaults to false.
   * @param ownerOnly If true, only returns documents owned by the user, not all accessible documents
   * @returns Promise<WrappedDocumentsResponse>
   */
  async list(options?: {
    ids?: string[];
    offset?: number;
    limit?: number;
    includeSummaryEmbeddings?: boolean;
    ownerOnly?: boolean;
  }): Promise<WrappedDocumentsResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
      include_summary_embeddings: options?.includeSummaryEmbeddings ?? false,
    };

    if (options?.ids?.length) {
      params.ids = options.ids;
    }

    if (options?.ownerOnly) {
      params.owner_only = options.ownerOnly;
    }

    return this.client.makeRequest("GET", "documents", {
      params,
    });
  }

  /**
   * Download a document's original file content.
   *
   * Note: Users can only download documents they own or have access to through collections.
   *
   * @param id ID of document to download
   * @returns Blob containing the document's file content
   */
  async download(options: { id: string }): Promise<Blob> {
    const response = await this.client.makeRequest(
      "GET",
      `documents/${options.id}/download`,
      {
        responseType: "arraybuffer",
        returnFullResponse: true, // Need full response to get headers
      },
    );

    if (!response.data) {
      throw new Error("No data received in response");
    }

    // Extract content-type, default if not present
    const contentType =
      response.headers?.["content-type"] || "application/octet-stream";

    // Handle different possible data types from axios
    if (response.data instanceof Blob) {
      // If it's already a Blob (less likely for arraybuffer type), return it
      return response.data;
    } else if (response.data instanceof ArrayBuffer) {
      // Common case for responseType: 'arraybuffer'
      return new Blob([response.data], { type: contentType });
    } else if (typeof response.data === "string") {
      // Less common, but handle if it returns a string
      return new Blob([response.data], { type: contentType });
    } else {
      // Try converting other types if necessary, fallback to empty blob
      try {
        return new Blob([JSON.stringify(response.data)], {
          type: contentType,
        });
      } catch (e) {
        console.error("Could not convert response data to Blob:", e);
        return new Blob([], { type: contentType }); // Return empty blob as fallback
      }
    }
  }

  /**
   * Export documents metadata as a CSV file.
   *
   * Note: This operation is typically restricted to superusers.
   *
   * @param options Export configuration options
   * @param options.outputPath Path where the CSV file should be saved (Node.js only). If provided, the function returns void.
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which documents are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   * @returns Promise<Blob> in browser environments (if outputPath is not provided), Promise<void> in Node.js (if outputPath is provided).
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

    const response = await this.client.makeRequest("POST", "documents/export", {
      data,
      responseType: "arraybuffer", // Expecting binary data for file saving / Blob creation
      headers: { Accept: "text/csv" },
      returnFullResponse: false, // We just need the data (ArrayBuffer)
    });

    // Node environment: write to file if outputPath is given
    if (options.outputPath && typeof process !== "undefined" && fs?.promises) {
      await fs.promises.writeFile(options.outputPath, Buffer.from(response));
      return; // Return void
    }

    // Browser or Node without outputPath: return Blob
    return new Blob([response], { type: "text/csv" });
  }

  /**
   * Export entities for a specific document as a CSV file.
   *
   * Note: This operation is typically restricted to superusers or owners of the document.
   *
   * @param options Export configuration options
   * @param options.id The ID of the document whose entities are to be exported.
   * @param options.outputPath Path where the CSV file should be saved (Node.js only). If provided, the function returns void.
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which entities are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   * @returns Promise<Blob> in browser environments (if outputPath is not provided), Promise<void> in Node.js (if outputPath is provided).
   */
  async exportEntities(options: {
    id: string;
    outputPath?: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<Blob | void> {
    const data: Record<string, any> = {
      // Router expects ID in path, not body. Data contains export options.
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
      `documents/${options.id}/entities/export`, // ID in path
      {
        data, // Export options in body
        responseType: "arraybuffer",
        headers: { Accept: "text/csv" },
        returnFullResponse: false,
      },
    );

    // Node environment: write to file if outputPath is given
    if (options.outputPath && typeof process !== "undefined" && fs?.promises) {
      await fs.promises.writeFile(options.outputPath, Buffer.from(response));
      return; // Return void
    }

    // Browser or Node without outputPath: return Blob
    return new Blob([response], { type: "text/csv" });
  }

  /**
   * Export entities for a document as a CSV file and trigger download in the browser.
   *
   * Note: This method only works in browser environments.
   * Note: Access control (superuser/owner) applies based on the underlying `exportEntities` call.
   *
   * @param options Export configuration options
   * @param options.filename The desired filename for the downloaded file (e.g., "entities.csv").
   * @param options.id The ID of the document whose entities are to be exported.
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which entities are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   */
  async exportEntitiesToFile(options: {
    filename: string;
    id: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<void> {
    if (typeof window === "undefined") {
      console.warn(
        "exportEntitiesToFile is intended for browser environments only.",
      );
      return;
    }
    // Call exportEntities without outputPath to get the Blob
    const blob = await this.exportEntities({
      id: options.id,
      columns: options.columns,
      filters: options.filters,
      includeHeader: options.includeHeader,
    });
    if (blob instanceof Blob) {
      downloadBlob(blob, options.filename);
    } else {
      // This case should not happen if outputPath is undefined, but handle defensively
      console.error(
        "Expected a Blob but received void. Did you accidentally provide an outputPath in a browser context?",
      );
    }
  }

  /**
   * Export relationships for a specific document as a CSV file.
   *
   * Note: This operation is typically restricted to superusers or owners of the document.
   *
   * @param options Export configuration options
   * @param options.id The ID of the document whose relationships are to be exported.
   * @param options.outputPath Path where the CSV file should be saved (Node.js only). If provided, the function returns void.
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which relationships are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   * @returns Promise<Blob> in browser environments (if outputPath is not provided), Promise<void> in Node.js (if outputPath is provided).
   */
  async exportRelationships(options: {
    id: string;
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
      `documents/${options.id}/relationships/export`, // ID in path
      {
        data, // Export options in body
        responseType: "arraybuffer",
        headers: { Accept: "text/csv" },
        returnFullResponse: false,
      },
    );

    // Node environment: write to file if outputPath is given
    if (options.outputPath && typeof process !== "undefined" && fs?.promises) {
      await fs.promises.writeFile(options.outputPath, Buffer.from(response));
      return; // Return void
    }

    // Browser or Node without outputPath: return Blob
    return new Blob([response], { type: "text/csv" });
  }

  /**
   * Export relationships for a document as a CSV file and trigger download in the browser.
   *
   * Note: This method only works in browser environments.
   * Note: Access control (superuser/owner) applies based on the underlying `exportRelationships` call.
   *
   * @param options Export configuration options
   * @param options.filename The desired filename for the downloaded file (e.g., "relationships.csv").
   * @param options.id The ID of the document whose relationships are to be exported.
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which relationships are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   */
  async exportRelationshipsToFile(options: {
    filename: string;
    id: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<void> {
    if (typeof window === "undefined") {
      console.warn(
        "exportRelationshipsToFile is intended for browser environments only.",
      );
      return;
    }
    const blob = await this.exportRelationships({
      id: options.id,
      columns: options.columns,
      filters: options.filters,
      includeHeader: options.includeHeader,
    });
    if (blob instanceof Blob) {
      downloadBlob(blob, options.filename);
    } else {
      console.error(
        "Expected a Blob but received void. Did you accidentally provide an outputPath in a browser context?",
      );
    }
  }

  /**
   * Download multiple documents as a zip file.
   *
   * Note: Access control applies. Non-superusers might be restricted to exporting only documents they own or have access to, and might be required to provide document IDs. Superusers can typically export any documents.
   *
   * @param options Configuration options for the zip download
   * @param options.documentIds Optional list of document IDs to include. May be required for non-superusers.
   * @param options.startDate Optional filter for documents created on or after this date.
   * @param options.endDate Optional filter for documents created on or before this date.
   * @param options.outputPath Optional path to save the zip file (Node.js only). If provided, the function returns void.
   * @returns Promise<Blob> in browser environments (if outputPath is not provided), Promise<void> in Node.js (if outputPath is provided).
   */
  async downloadZip(options: {
    documentIds?: string[];
    startDate?: Date;
    endDate?: Date;
    outputPath?: string;
  }): Promise<Blob | void> {
    const params: Record<string, any> = {};

    if (options.documentIds?.length) {
      // Pass as array, backend expects list
      params.document_ids = options.documentIds;
    }
    if (options.startDate) {
      params.start_date = options.startDate.toISOString();
    }
    if (options.endDate) {
      params.end_date = options.endDate.toISOString();
    }

    const response = await this.client.makeRequest(
      "GET",
      "documents/download_zip",
      {
        params,
        responseType: "arraybuffer",
        headers: { Accept: "application/zip" }, // Correct mime type
        returnFullResponse: false,
      },
    );

    // Node environment: write to file if outputPath is given
    if (options.outputPath && typeof process !== "undefined" && fs?.promises) {
      await fs.promises.writeFile(options.outputPath, Buffer.from(response));
      return; // Return void
    }

    // Browser or Node without outputPath: return Blob
    return new Blob([response], { type: "application/zip" });
  }

  /**
   * Download multiple documents as a zip file and trigger download in the browser.
   *
   * Note: This method only works in browser environments.
   * Note: Access control applies based on the underlying `downloadZip` call.
   *
   * @param options Configuration options for the zip download
   * @param options.filename The desired filename for the downloaded zip file (e.g., "documents.zip").
   * @param options.documentIds Optional list of document IDs to include.
   * @param options.startDate Optional filter for documents created on or after this date.
   * @param options.endDate Optional filter for documents created on or before this date.
   */
  async downloadZipToFile(options: {
    filename: string;
    documentIds?: string[];
    startDate?: Date;
    endDate?: Date;
  }): Promise<void> {
    if (typeof window === "undefined") {
      console.warn(
        "downloadZipToFile is intended for browser environments only.",
      );
      return;
    }
    const blob = await this.downloadZip({
      documentIds: options.documentIds,
      startDate: options.startDate,
      endDate: options.endDate,
    });
    if (blob instanceof Blob) {
      downloadBlob(blob, options.filename);
    } else {
      console.error(
        "Expected a Blob but received void. Did you accidentally provide an outputPath in a browser context?",
      );
    }
  }

  /**
   * Export documents metadata as a CSV file and trigger download in the browser.
   *
   * Note: This method only works in browser environments.
   * Note: Access control (superuser) applies based on the underlying `export` call.
   *
   * @param options Export configuration options
   * @param options.filename The desired filename for the downloaded CSV file (e.g., "export.csv").
   * @param options.columns Optional list of specific columns to include
   * @param options.filters Optional filters to limit which documents are exported
   * @param options.includeHeader Whether to include column headers (default: true)
   */
  async exportToFile(options: {
    filename: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<void> {
    if (typeof window === "undefined") {
      console.warn("exportToFile is intended for browser environments only.");
      return;
    }
    const blob = await this.export({
      columns: options.columns,
      filters: options.filters,
      includeHeader: options.includeHeader,
    });
    if (blob instanceof Blob) {
      downloadBlob(blob, options.filename);
    } else {
      console.error(
        "Expected a Blob but received void. Did you accidentally provide an outputPath in a browser context?",
      );
    }
  }

  /**
   * Delete a specific document by ID. This also deletes associated chunks.
   *
   * Note: Users can typically only delete documents they own. Superusers may have broader access.
   *
   * @param id ID of document to delete
   * @returns Promise<WrappedBooleanResponse>
   */
  async delete(options: { id: string }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `documents/${options.id}`);
  }

  /**
   * Get chunks for a specific document.
   *
   * Note: Users can only access chunks from documents they own or have access to through collections.
   *
   * @param id Document ID to retrieve chunks for
   * @param includeVectors Whether to include vector embeddings in the response (default: false)
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 1000. Defaults to 100.
   * @returns Promise<WrappedChunksResponse>
   */
  async listChunks(options: {
    id: string;
    includeVectors?: boolean;
    offset?: number;
    limit?: number;
  }): Promise<WrappedChunksResponse> {
    const params: Record<string, any> = {
      // Map to snake_case for the API
      include_vectors: options.includeVectors ?? false,
      offset: options.offset ?? 0,
      limit: options.limit ?? 100,
    };

    return this.client.makeRequest("GET", `documents/${options.id}/chunks`, {
      params,
    });
  }

  /**
   * List collections associated with a specific document.
   *
   * Note: This endpoint might be restricted to superusers depending on API implementation. Check API documentation.
   *
   * @param id ID of document to retrieve collections for
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 1000. Defaults to 100.
   * @returns Promise<WrappedCollectionsResponse>
   */
  async listCollections(options: {
    id: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedCollectionsResponse> {
    const params: Record<string, any> = {
      offset: options.offset ?? 0,
      limit: options.limit ?? 100,
    };

    return this.client.makeRequest(
      "GET",
      `documents/${options.id}/collections`,
      {
        params,
      },
    );
  }

  /**
   * Delete documents based on metadata filters.
   *
   * Note: For non-superusers, deletion is implicitly limited to documents owned by the user, in addition to the provided filters.
   *
   * @param filters Filters to apply when selecting documents to delete (e.g., `{ "metadata.year": { "$lt": 2020 } }`)
   * @returns Promise<WrappedBooleanResponse>
   */
  async deleteByFilter(options: {
    filters: Record<string, any>;
  }): Promise<WrappedBooleanResponse> {
    // Filters are sent in the request body as JSON
    return this.client.makeRequest("DELETE", "documents/by-filter", {
      data: options.filters,
    });
  }

  /**
   * Triggers the extraction of entities and relationships from a document.
   *
   * Note: Users typically need to own the document to trigger extraction. Superusers may have broader access.
   * This is often an asynchronous process.
   *
   * @param id ID of the document to extract from.
   * @param settings Optional settings to override the default extraction configuration.
   * @param runWithOrchestration Whether to run with orchestration (recommended, default: true).
   * @returns Promise<WrappedGenericMessageResponse> indicating the task was queued or completed.
   */
  async extract(options: {
    id: string;
    settings?: Record<string, any>; // Changed from runType
    runWithOrchestration?: boolean;
  }): Promise<WrappedGenericMessageResponse> {
    const data: Record<string, any> = {};

    if (options.settings) {
      // Send settings in the body as per router
      data.settings = options.settings;
    }
    if (options.runWithOrchestration !== undefined) {
      // Send runWithOrchestration in the body
      data.run_with_orchestration = options.runWithOrchestration;
    }

    return this.client.makeRequest("POST", `documents/${options.id}/extract`, {
      // Data goes in the body for POST
      data: data,
    });
  }

  /**
   * Retrieves the entities that were extracted from a document.
   *
   * Note: Users can only access entities from documents they own or have access to through collections.
   *
   * @param id Document ID to retrieve entities for
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 1000. Defaults to 100.
   * @param includeEmbeddings Whether to include vector embeddings in the response (default: false). Renamed from includeVectors for consistency with router.
   * @returns Promise<WrappedEntitiesResponse>
   */
  async listEntities(options: {
    id: string;
    offset?: number;
    limit?: number;
    includeEmbeddings?: boolean; // Changed name to match router param
  }): Promise<WrappedEntitiesResponse> {
    const params: Record<string, any> = {
      offset: options.offset ?? 0,
      limit: options.limit ?? 100,
      // Map to snake_case for the API
      include_embeddings: options.includeEmbeddings ?? false,
    };

    return this.client.makeRequest("GET", `documents/${options.id}/entities`, {
      params,
    });
  }

  /**
   * Retrieves the relationships between entities that were extracted from a document.
   *
   * Note: Users can only access relationships from documents they own or have access to through collections.
   *
   * @param id Document ID to retrieve relationships for
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 1000. Defaults to 100.
   * @param entityNames Optional filter for relationships involving specific entity names.
   * @param relationshipTypes Optional filter for specific relationship types.
   * @returns Promise<WrappedRelationshipsResponse>
   */
  async listRelationships(options: {
    id: string;
    offset?: number;
    limit?: number;
    // includeVectors?: boolean; // This param doesn't exist on the router for relationships
    entityNames?: string[];
    relationshipTypes?: string[];
  }): Promise<WrappedRelationshipsResponse> {
    const params: Record<string, any> = {
      offset: options.offset ?? 0,
      limit: options.limit ?? 100,
    };
    // Add optional filters if provided
    if (options.entityNames?.length) {
      params.entity_names = options.entityNames;
    }
    if (options.relationshipTypes?.length) {
      params.relationship_types = options.relationshipTypes;
    }

    return this.client.makeRequest(
      "GET",
      `documents/${options.id}/relationships`,
      {
        params,
      },
    );
  }

  /**
   * Triggers the deduplication of entities within a document.
   *
   * Note: Users typically need to own the document to trigger deduplication. Superusers may have broader access.
   * This is often an asynchronous process.
   *
   * @param id Document ID to deduplicate entities for.
   * @param settings Optional settings to override the default deduplication configuration.
   * @param runWithOrchestration Whether to run with orchestration (recommended, default: true).
   * @returns Promise<WrappedGenericMessageResponse> indicating the task was queued or completed.
   */
  async deduplicate(options: {
    id: string;
    // runType?: string; // Removed, router expects settings
    settings?: Record<string, any>; // Use settings as per router
    runWithOrchestration?: boolean;
  }): Promise<WrappedGenericMessageResponse> {
    const data: Record<string, any> = {};

    // Removed runType
    if (options.settings) {
      data.settings = options.settings; // Send settings in body
    }
    if (options.runWithOrchestration !== undefined) {
      data.run_with_orchestration = options.runWithOrchestration; // Send in body
    }

    return this.client.makeRequest(
      "POST",
      `documents/${options.id}/deduplicate`,
      {
        // Data goes in the body for POST
        data: data,
      },
    );
  }

  /**
   * Perform a search query on document summaries.
   *
   * Note: Access control (based on user ownership/collection access) is applied to the search results.
   *
   * @param query The search query string.
   * @param searchMode The search mode to use ('basic', 'advanced', 'custom'). Defaults to 'custom'.
   * @param searchSettings Optional settings to configure the search (filters, limits, hybrid search options, etc.).
   * @returns Promise<WrappedDocumentSearchResponse>
   */
  async search(options: {
    query: string;
    searchMode?: SearchMode;
    searchSettings?: SearchSettings;
  }): Promise<WrappedDocumentSearchResponse> {
    const data: Record<string, any> = {
      query: options.query,
      // Map to snake_case for API
      search_mode: options.searchMode ?? "custom",
      search_settings: options.searchSettings ?? {}, // Send empty object if undefined
    };

    return this.client.makeRequest("POST", "documents/search", {
      data: data, // Use data for POST body
    });
  }

  /**
   * Ingest a sample document into R2R. Downloads a sample PDF, ingests it, and cleans up.
   *
   * Note: This requires Node.js environment with 'fs', 'axios', 'os', 'path', 'uuid' modules. It will not work directly in a standard browser environment due to file system access.
   *
   * @param options Optional ingestion options.
   * @param options.ingestionMode If provided, passes the ingestion mode (e.g. "hi-res") to the create() method.
   * @returns Promise<WrappedIngestionResponse> The ingestion response.
   */
  async createSample(options?: {
    ingestionMode?: "hi-res" | "fast" | "custom" | "ocr";
  }): Promise<WrappedIngestionResponse> {
    // Check if in Node.js environment
    if (typeof window !== "undefined" || !fs || !axios || !os || !path) {
      throw new Error(
        "createSample method requires a Node.js environment with 'fs', 'axios', 'os', 'path', 'uuid' modules.",
      );
    }

    const sampleFileUrl =
      "https://raw.githubusercontent.com/SciPhi-AI/R2R/main/py/core/examples/data/DeepSeek_R1.pdf";
    const parsedUrl = new URL(sampleFileUrl);
    const filename = parsedUrl.pathname.split("/").pop() || "sample.pdf"; // Default to .pdf

    // Create a temporary file path using Node.js 'os' and 'path'
    const tmpDir = os.tmpdir();
    const tmpFilePath = path.join(
      tmpDir,
      `r2r_sample_${Date.now()}_${filename}`,
    );

    let ingestionResponse: WrappedIngestionResponse;

    try {
      // Download the file using axios
      const response = await axios.get(sampleFileUrl, {
        responseType: "arraybuffer", // Get data as ArrayBuffer
      });

      // Write the downloaded file to the temporary location using Node.js 'fs'
      await fs.promises.writeFile(tmpFilePath, Buffer.from(response.data)); // Convert ArrayBuffer to Buffer

      // Generate a stable document ID using uuid v5
      const NAMESPACE_DNS = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"; // Standard DNS namespace UUID
      const docId = uuidv5(sampleFileUrl, NAMESPACE_DNS);
      const metadata = { title: filename };

      // Ingest the file by calling the create() method, passing the file path
      ingestionResponse = await this.create({
        file: tmpFilePath, // Pass the path as string (Node.js compatible part of create)
        metadata,
        id: docId,
        ingestionMode: options?.ingestionMode,
      });
    } catch (error) {
      // Ensure cleanup happens even on error during download or ingestion
      console.error("Error during createSample:", error);
      throw error; // Re-throw the error after logging
    } finally {
      // Clean up: remove the temporary file using Node.js 'fs'
      try {
        await fs.promises.unlink(tmpFilePath);
      } catch (unlinkError) {
        // Log unlink error but don't overwrite original error if one occurred
        console.error(
          `Failed to delete temporary file ${tmpFilePath}:`,
          unlinkError,
        );
      }
    }
    return ingestionResponse;
  }
}
