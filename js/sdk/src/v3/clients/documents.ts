import { r2rClient } from "../../r2rClient";
import FormData from "form-data";

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
   * @param content Optional text content to upload, if no file path is provided
   * @param id Optional ID to assign to the document
   * @param collectionIds Collection IDs to associate with the document. If none are provided, the document will be assigned to the user's default collection.
   * @param metadata Optional metadata to assign to the document
   * @param ingestionConfig Optional ingestion configuration to use
   * @param runWithOrchestration Optional flag to run with orchestration
   * @returns
   */
  async create(options: {
    file?: FileInput;
    content?: string;
    id?: string;
    metadata?: Record<string, any>;
    ingestionConfig?: Record<string, any>;
    collectionIds?: string[];
    runWithOrchestration?: boolean;
  }): Promise<any> {
    if (!options.file && !options.content) {
      throw new Error("Either file or content must be provided");
    }

    if (options.file && options.content) {
      throw new Error("Cannot provide both file and content");
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

    if (options.content) {
      formData.append("content", options.content);
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
      formData.append("collection_ids", JSON.stringify(options.collectionIds));
    }
    if (options.runWithOrchestration !== undefined) {
      formData.append(
        "run_with_orchestration",
        String(options.runWithOrchestration),
      );
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
   * Update an existing document.
   * @param id ID of document to update
   * @param file Optional new file to ingest
   * @param content Optional new text content
   * @param metadata Optional new metadata
   * @param ingestionConfig Custom ingestion configuration
   * @param runWithOrchestration Whether to run with orchestration
   * @returns
   */
  async update(options: {
    id: string;
    file?: FileInput;
    content?: string;
    metadata?: Record<string, any>;
    ingestionConfig?: Record<string, any>;
    runWithOrchestration?: boolean;
  }): Promise<any> {
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
            throw new Error("Directories are not supported in update()");
          } else {
            appendFile(fs.createReadStream(path), path.split("/").pop() || "");
          }
        } else {
          console.warn(
            "File path provided in browser environment. This is not supported.",
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

    if (options.content) {
      formData.append("content", options.content);
    }
    if (options.metadata) {
      formData.append("metadata", JSON.stringify([options.metadata]));
    }
    if (options.ingestionConfig) {
      formData.append(
        "ingestion_config",
        JSON.stringify(options.ingestionConfig),
      );
    }
    if (options.runWithOrchestration !== undefined) {
      formData.append(
        "run_with_orchestration",
        String(options.runWithOrchestration),
      );
    }

    formData.append("file_names", JSON.stringify(processedFiles));

    return this.client.makeRequest("POST", `documents/${options.id}`, {
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
  async retrieve(options: { id: string }): Promise<any> {
    return this.client.makeRequest("GET", `documents/${options.id}`);
  }

  /**
   * List documents with pagination.
   * @param ids Optional list of document IDs to filter by
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async list(options?: {
    ids?: string[];
    offset?: number;
    limit?: number;
  }): Promise<any> {
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
  async download(options: { id: string }): Promise<any> {
    return this.client.makeRequest("GET", `documents/${options.id}/download`, {
      responseType: "blob",
    });
  }

  /**
   * Delete a specific document.
   * @param id ID of document to delete
   * @returns
   */
  async delete(options: { id: string }): Promise<any> {
    return this.client.makeRequest("DELETE", `documents/${options.id}`);
  }

  /**
   * Get chunks for a specific document.
   * @param id Document ID to retrieve chunks for
   * @param include_vectors Whether to include vectors in the response
   * @param offset Specifies the number of objects to skip. Defaults to 0.
   * @param limit Specifies a limit on the number of objects to return, ranging between 1 and 100. Defaults to 100.
   * @returns
   */
  async listChunks(options: {
    id: string;
    include_vectors?: boolean;
    offset?: number;
    limit?: number;
  }): Promise<any> {
    const params: Record<string, any> = {
      include_vectors: options.include_vectors ?? false,
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
  async listCollections(options: {
    id: string;
    offset?: number;
    limit?: number;
  }): Promise<any> {
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

  async deleteByFilter(options: {
    filters: Record<string, any>;
  }): Promise<any> {
    return this.client.makeRequest("DELETE", "documents/by-filter", {
      data: options.filters,
    });
  }
}
