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

  async create(options: {
    file?: FileInput;
    content?: string;
    id?: string;
    metadata?: Record<string, any>;
    ingestionConfig?: Record<string, any>;
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
      formData.append("id", JSON.stringify(options.id));
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

  async retrieve(id: string): Promise<any> {
    return this.client.makeRequest("GET", `documents/${id}`);
  }

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

  async download(id: string): Promise<any> {
    return this.client.makeRequest("GET", `documents/${id}/download`, {
      responseType: "blob",
    });
  }

  async list_chunks(options: {
    id: string;
    offset?: number;
    limit?: number;
    include_vectors?: boolean;
  }): Promise<any> {
    const params: Record<string, any> = {
      offset: options.offset ?? 0,
      limit: options.limit ?? 100,
      include_vectors: options.include_vectors ?? false,
    };

    return this.client.makeRequest("GET", `documents/${options.id}/chunks`, {
      params,
    });
  }

  async list_collections(options: {
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

  async delete_by_filter(filters: Record<string, any>): Promise<any> {
    return this.client.makeRequest("DELETE", "documents/by-filter", {
      data: filters,
    });
  }

  async delete(id: string): Promise<any> {
    return this.client.makeRequest("DELETE", `documents/${id}`);
  }
}
