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
} from "../../types";
import { feature } from "../../feature";

let fs: any;
if (typeof window === "undefined") {
  import("fs").then((module) => {
    fs = module;
  });
}

type FileInput = string | File | { path: string; name: string };

export class DocumentsClient {
  constructor(private client: r2rClient) {}

  /**
   * Create a new document from either a file or content.
   * @param file The file to upload, if any
   * @param raw_text Optional raw text content to upload, if no file path is provided
   * @param chunks Optional array of pre-processed text chunks to ingest
   * @param id Optional ID to assign to the document
   * @param collectionIds Collection IDs to associate with the document. If none are provided, the document will be assigned to the user's default collection.
   * @param metadata Optional metadata to assign to the document
   * @param ingestionConfig Optional ingestion configuration to use
   * @param runWithOrchestration Optional flag to run with orchestration
   * @returns
   */
  @feature("documents.create")
  async create(options: {
    file?: FileInput;
    raw_text?: string;
    chunks?: string[];
    id?: string;
    metadata?: Record<string, any>;
    ingestionConfig?: Record<string, any>;
    collectionIds?: string[];
    runWithOrchestration?: boolean;
    ingestionMode?: "hi-res" | "fast" | "custom";
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
    const processedFiles: string[] = [];

    const processPath = async (path: FileInput): Promise<void> => {
      const appendFile = (
        file: File | NodeJS.ReadableStream,
        filename: string,
      ) => {
        formData.append(`file`, file, filename);
        processedFiles.push(filename);
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
            "File or folder path provided in browser environment. This is not supported.",
          );
        }
      } else if (path instanceof File) {
        appendFile(path, path.name);
      } else if ("path" in path && "name" in path) {
        if (typeof window === "undefined") {
          appendFile(fs.createReadStream(path.path), path.name);
        } else {
          console.warn(
            "File path provided in browser environment. This is not supported.",
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
        JSON.stringify(options.ingestionConfig),
      );
    }
    if (options.collectionIds) {
      options.collectionIds.forEach((id) => {
        formData.append("collection_ids", id);
      });
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

    formData.append("file_names", JSON.stringify(processedFiles));

    return this.client.makeRequest("POST", "documents", {
      data: formData,
      headers: formData.getHeaders?.() ?? {
        "Content-Type": "multipart/form-data",
      },
      transformRequest: [
        (data: any, headers: Record<string, string>) => {
          delete headers["Content-Type"];
          return data;
        },
      ],
    });
  }

  /**
   * Get a specific document by ID.
   * @param ids Optional list of document IDs to filter by
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  @feature("documents.retrieve")
  async retrieve(options: { id: string }): Promise<WrappedDocumentResponse> {
    return this.client.makeRequest("GET", `documents/${options.id}`);
  }

  /**
   * List documents with pagination.
   * @param ids Optional list of document IDs to filter by
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  @feature("documents.list")
  async list(options?: {
    ids?: string[];
    offset?: number;
    limit?: number;
  }): Promise<WrappedDocumentsResponse> {
    const params: Record<string, any> = {
      offset: options?.offset ?? 0,
      limit: options?.limit ?? 100,
    };

    if (options?.ids) {
      params.ids = options.ids;
    }

    return this.client.makeRequest("GET", "documents", {
      params,
    });
  }

  /**
   * Download a document's file content.
   * @param id ID of document to download
   * @returns
   */
  @feature("documents.download")
  async download(options: { id: string }): Promise<any> {
    return this.client.makeRequest("GET", `documents/${options.id}/download`, {
      responseType: "blob",
    });
  }

  /**
   * Export documents as a CSV file. This method supports filtering the exported data
   * and customizing which columns are included in the output.
   *
   * The data is streamed directly from the server to minimize memory usage and
   * handle large exports efficiently.
   *
   * @param options Configuration options for the export
   * @param options.columns Optional list of specific columns to include in the export
   * @param options.filters Optional filters to limit which documents are exported
   * @param options.includeHeader Whether to include column headers in the CSV (default: true)
   * @returns A Blob containing the CSV data
   */
  @feature("documents.export")
  async export(options?: {
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<Blob> {
    const data: Record<string, any> = {
      include_header: options?.includeHeader ?? true,
    };

    if (options?.columns) {
      data.columns = options.columns;
    }

    if (options?.filters) {
      data.filters = options.filters;
    }

    return this.client.makeRequest("POST", "documents/export", {
      data,
      responseType: "blob",
      headers: {
        Accept: "text/csv",
      },
    });
  }

  /**
   * Export documents as a CSV file and save it to the user's device.
   * @param filename
   * @param options
   */
  @feature("documents.exportToFile")
  async exportToFile(options: {
    filename: string;
    columns?: string[];
    filters?: Record<string, any>;
    includeHeader?: boolean;
  }): Promise<void> {
    const blob = await this.export(options);

    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = options.filename;
    document.body.appendChild(link);
    link.click();

    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  }

  /**
   * Delete a specific document.
   * @param id ID of document to delete
   * @returns
   */
  @feature("documents.delete")
  async delete(options: { id: string }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", `documents/${options.id}`);
  }

  /**
   * Get chunks for a specific document.
   * @param id Document ID to retrieve chunks for
   * @param includeVectors Whether to include vectors in the response
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  @feature("documents.listChunks")
  async listChunks(options: {
    id: string;
    includeVectors?: boolean;
    offset?: number;
    limit?: number;
  }): Promise<WrappedChunksResponse> {
    const params: Record<string, any> = {
      includeVectors: options.includeVectors ?? false,
      offset: options.offset ?? 0,
      limit: options.limit ?? 100,
    };

    return this.client.makeRequest("GET", `documents/${options.id}/chunks`, {
      params,
    });
  }

  /**
   * List collections for a specific document.
   * @param id ID of document to retrieve collections for
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  @feature("documents.listCollections")
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

  @feature("documents.deleteByFilter")
  async deleteByFilter(options: {
    filters: Record<string, any>;
  }): Promise<WrappedBooleanResponse> {
    return this.client.makeRequest("DELETE", "documents/by-filter", {
      data: options.filters,
    });
  }

  /**
   * Extracts entities and relationships from a document.
   *
   * The entities and relationships extraction process involves:
   *  1. Parsing documents into semantic chunks
   *  2. Extracting entities and relationships using LLMs
   * @param options
   * @returns
   */
  @feature("documents.extract")
  async extract(options: {
    id: string;
    runType?: string;
    runWithOrchestration?: boolean;
  }): Promise<any> {
    const data: Record<string, any> = {};

    if (options.runType) {
      data.runType = options.runType;
    }
    if (options.runWithOrchestration !== undefined) {
      data.runWithOrchestration = options.runWithOrchestration;
    }

    return this.client.makeRequest("POST", `documents/${options.id}/extract`, {
      data,
    });
  }

  /**
   * Retrieves the entities that were extracted from a document. These
   * represent important semantic elements like people, places,
   * organizations, concepts, etc.
   *
   * Users can only access entities from documents they own or have access
   * to through collections. Entity embeddings are only included if
   * specifically requested.
   *
   * Results are returned in the order they were extracted from the document.
   * @param id Document ID to retrieve entities for
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @param includeEmbeddings Whether to include vector embeddings in the response.
   * @returns
   */
  @feature("documents.listEntities")
  async listEntities(options: {
    id: string;
    offset?: number;
    limit?: number;
    includeVectors?: boolean;
  }): Promise<WrappedEntitiesResponse> {
    const params: Record<string, any> = {
      offset: options.offset ?? 0,
      limit: options.limit ?? 100,
      includeVectors: options.includeVectors ?? false,
    };

    return this.client.makeRequest("GET", `documents/${options.id}/entities`, {
      params,
    });
  }

  /**
   * Retrieves the relationships between entities that were extracted from
   * a document. These represent connections and interactions between
   * entities found in the text.
   *
   * Users can only access relationships from documents they own or have
   * access to through collections. Results can be filtered by entity names
   * and relationship types.
   *
   * Results are returned in the order they were extracted from the document.
   * @param id Document ID to retrieve relationships for
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @param includeEmbeddings Whether to include vector embeddings in the response.
   * @param entityNames Filter relationships by specific entity names.
   * @param relationshipTypes Filter relationships by specific relationship types.
   * @returns WrappedRelationshipsResponse
   */
  @feature("documents.listRelationships")
  async listRelationships(options: {
    id: string;
    offset?: number;
    limit?: number;
    includeVectors?: boolean;
    entityNames?: string[];
    relationshipTypes?: string[];
  }): Promise<WrappedRelationshipsResponse> {
    const params: Record<string, any> = {
      offset: options.offset ?? 0,
      limit: options.limit ?? 100,
      includeVectors: options.includeVectors ?? false,
    };

    return this.client.makeRequest(
      "GET",
      `documents/${options.id}/relationships`,
      {
        params,
      },
    );
  }
}
