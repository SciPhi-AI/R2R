import axios, { Method } from "axios";
import FormData from "form-data";

import { BaseClient } from "./baseClient";

import { ChunksClient } from "./v3/clients/chunks";
import { CollectionsClient } from "./v3/clients/collections";
import { ConversationsClient } from "./v3/clients/conversations";
import { DocumentsClient } from "./v3/clients/documents";
import { GraphsClient } from "./v3/clients/graphs";
import { IndiciesClient } from "./v3/clients/indices";
import { PromptsClient } from "./v3/clients/prompts";
import { RetrievalClient } from "./v3/clients/retrieval";
import { SystemClient } from "./v3/clients/system";
import { UsersClient } from "./v3/clients/users";

let fs: any;
if (typeof window === "undefined") {
  import("fs").then((module) => {
    fs = module;
  });
}

import { feature, initializeTelemetry } from "./feature";
import {
  LoginResponse,
  TokenInfo,
  Message,
  RefreshTokenResponse,
  KGRunType,
  KGEntityDeduplicationSettings,
  RawChunk,
} from "./models";

export class r2rClient extends BaseClient {
  public readonly chunks: ChunksClient;
  public readonly collections: CollectionsClient;
  public readonly conversations: ConversationsClient;
  public readonly documents: DocumentsClient;
  public readonly graphs: GraphsClient;
  public readonly indices: IndiciesClient;
  public readonly prompts: PromptsClient;
  public readonly retrieval: RetrievalClient;
  public readonly system: SystemClient;
  public readonly users: UsersClient;

  constructor(baseURL: string, anonymousTelemetry = true) {
    super(baseURL, "", anonymousTelemetry);

    this.chunks = new ChunksClient(this);
    this.collections = new CollectionsClient(this);
    this.conversations = new ConversationsClient(this);
    this.documents = new DocumentsClient(this);
    this.graphs = new GraphsClient(this);
    this.indices = new IndiciesClient(this);
    this.prompts = new PromptsClient(this);
    this.retrieval = new RetrievalClient(this);
    this.system = new SystemClient(this);
    this.users = new UsersClient(this);

    initializeTelemetry(this.anonymousTelemetry);

    this.axiosInstance = axios.create({
      baseURL: this.baseUrl,
      headers: {
        "Content-Type": "application/json",
      },
      paramsSerializer: (params) => {
        const parts: string[] = [];
        Object.entries(params).forEach(([key, value]) => {
          if (Array.isArray(value)) {
            value.forEach((v) =>
              parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(v)}`),
            );
          } else {
            parts.push(
              `${encodeURIComponent(key)}=${encodeURIComponent(value)}`,
            );
          }
        });
        return parts.join("&");
      },
      transformRequest: [
        (data) => {
          if (typeof data === "string") {
            return data;
          }
          return JSON.stringify(data);
        },
      ],
    });
  }

  public makeRequest<T = any>(
    method: Method,
    endpoint: string,
    options: any = {},
  ): Promise<T> {
    return this._makeRequest(method, endpoint, options, "v3");
  }

  public getRefreshToken(): string | null {
    return this.refreshToken;
  }

  setTokens(accessToken: string | null, refreshToken: string | null): void {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }

  // -----------------------------------------------------------------------------
  //
  // Auth
  //
  // -----------------------------------------------------------------------------
  /**
   * Registers a new user with the given email and password.
   * @param email The email of the user to register.
   * @param password The password of the user to register.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.users.register` instead.
   */

  @feature("register")
  async register(email: string, password: string): Promise<any> {
    return await this._makeRequest("POST", "register", {
      data: { email, password },
    });
  }

  /**
   * Verifies the email of a user with the given verification code.
   * @param verification_code The verification code to verify the email with.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.users.verifyEmail` instead.
   */
  @feature("verifyEmail")
  async verifyEmail(email: string, verification_code: string): Promise<any> {
    return await this._makeRequest("POST", "verify_email", {
      data: { email, verification_code },
    });
  }

  /**
   * Attempts to log in a user with the given email and password.
   * @param email The email of the user to log in.
   * @param password The password of the user to log in.
   * @returns A promise that resolves to the response from the server containing the access and refresh tokens.
   * @deprecated Use `client.users.login` instead.
   */
  @feature("login")
  async login(
    email: string,
    password: string,
  ): Promise<{ access_token: TokenInfo; refresh_token: TokenInfo }> {
    const data = {
      username: email,
      password: password,
    };

    const response = await this._makeRequest<LoginResponse>("POST", "login", {
      data: data,
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
      },
    });

    if (response && response.results) {
      this.accessToken = response.results.access_token.token;
      this.refreshToken = response.results.refresh_token.token;
    } else {
      throw new Error("Invalid response structure");
    }

    return response.results;
  }

  /**
   * Logs in a user using a token.
   * @param accessToken The access token to use for authentication.
   * @returns A promise that resolves to the response from the server containing the access token.
   * @deprecated Use `client.users.loginWithToken` instead.
   */
  @feature("loginWithToken")
  async loginWithToken(
    accessToken: string,
  ): Promise<{ accessToken: TokenInfo }> {
    this.accessToken = accessToken;

    try {
      await this._makeRequest("GET", "user");

      return {
        accessToken: {
          token: accessToken,
          tokenType: "access_token",
        },
      };
    } catch (error) {
      this.accessToken = null;
      throw new Error("Invalid token provided");
    }
  }

  /**
   * Logs out the currently authenticated user.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.users.logout` instead.
   */
  @feature("logout")
  async logout(): Promise<any> {
    this._ensureAuthenticated();

    const response = await this._makeRequest("POST", "logout");
    this.accessToken = null;
    this.refreshToken = null;
    return response;
  }

  /**
   * Retrieves the user information for the currently authenticated user.
   * @returns A promise that resolves to the response from the server containing the user information.
   * @deprecated Use `client.users.list` instead.
   */
  @feature("user")
  async user(): Promise<any> {
    this._ensureAuthenticated();
    return await this._makeRequest("GET", "user");
  }

  /**
   * Updates the profile information for the currently authenticated user.
   * @param email The updated email for the user.
   * @param name The updated name for the user.
   * @param bio  The updated bio for the user.
   * @param profilePicture The updated profile picture URL for the user.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.users.update` instead.
   */
  @feature("updateUser")
  async updateUser(
    userId: string,
    email?: string,
    isSuperuser?: boolean,
    name?: string,
    bio?: string,
    profilePicture?: string,
  ): Promise<any> {
    this._ensureAuthenticated();

    let data: Record<string, any> = { user_id: userId };
    if (email !== undefined) {
      data.email = email;
    }
    if (isSuperuser !== undefined) {
      data.is_superuser = isSuperuser;
    }
    if (name !== undefined) {
      data.name = name;
    }
    if (bio !== undefined) {
      data.bio = bio;
    }
    if (profilePicture !== undefined) {
      data.profile_picture = profilePicture;
    }

    return await this._makeRequest("PUT", "user", { data });
  }

  /**
   * Refreshes the access token for the currently authenticated user.
   * @returns A promise that resolves to the response from the server containing the new access and refresh tokens.
   * @deprecated Use `client.users.refreshAccessToken` instead.
   */
  async refreshAccessToken(): Promise<RefreshTokenResponse> {
    if (!this.refreshToken) {
      throw new Error("No refresh token available. Please login again.");
    }

    const response = await this._makeRequest<RefreshTokenResponse>(
      "POST",
      "refresh_access_token",
      {
        data: this.refreshToken,
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
      },
    );

    if (response && response.results) {
      this.accessToken = response.results.access_token.token;
      this.refreshToken = response.results.refresh_token.token;
    } else {
      throw new Error("Invalid response structure");
    }

    return response;
  }

  /**
   * Changes the password of the currently authenticated user.
   * @param current_password The current password of the user.
   * @param new_password The new password to set for the user.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.users.changePassword` instead.
   */
  @feature("changePassword")
  async changePassword(
    current_password: string,
    new_password: string,
  ): Promise<any> {
    this._ensureAuthenticated();

    return this._makeRequest("POST", "change_password", {
      data: {
        current_password,
        new_password,
      },
    });
  }

  /**
   * Requests a password reset for the user with the given email.
   * @param email The email of the user to request a password reset for.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.users.requestPasswordReset` instead.
   */
  @feature("requestPasswordReset")
  async requestPasswordReset(email: string): Promise<any> {
    return await this._makeRequest("POST", "request_password_reset", {
      data: JSON.stringify(email),
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  /**
   * Confirms a password reset for the user with the given reset token.
   * @param resetToken The reset token to confirm the password reset with.
   * @param newPassword The new password to set for the user.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.users.resetPassword` instead.
   */
  @feature("confirmPasswordReset")
  async confirmPasswordReset(
    resetToken: string,
    newPassword: string,
  ): Promise<any> {
    return this._makeRequest("POST", `reset_password/${resetToken}`, {
      data: { new_password: newPassword },
    });
  }

  /**
   * Deletes the user with the given user ID.
   * @param user_id The ID of the user to delete, defaults to the currently authenticated user.
   * @param password The password of the user to delete.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.users.delete` instead.
   */
  @feature("deleteUser")
  async deleteUser(userId: string, password?: string): Promise<any> {
    this._ensureAuthenticated();
    return await this._makeRequest("DELETE", `user/${userId}`, {
      data: { password },
    });
  }

  /**
   * Generates a new verification code and sends a reset email to the user.
   * @param email The email address of the user to send the reset email to.
   * @returns A promise that resolves to the verification code and message from the server.
   */
  @feature("sendResetEmail")
  async sendResetEmail(email: string): Promise<Record<string, any>> {
    return await this._makeRequest("POST", "send_reset_email", {
      data: { email },
    });
  }
  // -----------------------------------------------------------------------------
  //
  // Ingestion
  //
  // -----------------------------------------------------------------------------

  // TODO: Need to update to closer match the Python SDK.
  /**
   * Ingest files into your R2R deployment.
   * @param files
   * @param options
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.documents.create` instead.
   */
  @feature("ingestFiles")
  async ingestFiles(
    files: (string | File | { path: string; name: string })[],
    options: {
      metadatas?: Record<string, any>[];
      document_ids?: string[];
      user_ids?: (string | null)[];
      ingestion_config?: Record<string, any>;
      collection_ids?: string[];
      run_with_orchestration?: boolean;
    } = {},
  ): Promise<any> {
    this._ensureAuthenticated();

    const formData = new FormData();
    const processedFiles: string[] = [];

    const processPath = async (
      path: string | File | { path: string; name: string },
      index: number,
    ): Promise<void> => {
      const appendFile = (
        file: File | NodeJS.ReadableStream,
        filename: string,
      ) => {
        formData.append(`files`, file, filename);
        processedFiles.push(filename);
      };

      if (typeof path === "string") {
        if (typeof window === "undefined") {
          const stat = await fs.promises.stat(path);
          if (stat.isDirectory()) {
            const files = await fs.promises.readdir(path, {
              withFileTypes: true,
            });
            for (const file of files) {
              await processPath(`${path}/${file.name}`, index);
            }
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

    for (let i = 0; i < files.length; i++) {
      await processPath(files[i], i);
    }

    const data: Record<string, string | undefined> = {
      metadatas: options.metadatas
        ? JSON.stringify(options.metadatas)
        : undefined,
      document_ids: options.document_ids
        ? JSON.stringify(options.document_ids)
        : undefined,
      user_ids: options.user_ids ? JSON.stringify(options.user_ids) : undefined,
      ingestion_config: options.ingestion_config
        ? JSON.stringify(options.ingestion_config)
        : undefined,
      collection_ids: options.collection_ids
        ? JSON.stringify(options.collection_ids)
        : undefined,
      run_with_orchestration:
        options.run_with_orchestration != undefined
          ? String(options.run_with_orchestration)
          : undefined,
    };

    Object.entries(data).forEach(([key, value]) => {
      if (value !== undefined) {
        formData.append(key, value);
      }
    });

    formData.append("file_names", JSON.stringify(processedFiles));

    return await this._makeRequest("POST", "ingest_files", {
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
   * Update existing files in your R2R deployment.
   * @param files
   * @param options
   * @returns
   * @deprecated Use `client.documents.update` instead.
   */
  @feature("updateFiles")
  async updateFiles(
    files: (File | { path: string; name: string })[],
    options: {
      document_ids: string[];
      metadatas?: Record<string, any>[];
      ingestion_config?: Record<string, any>;
      collection_ids?: string[];
      run_with_orchestration?: boolean;
    },
  ): Promise<any> {
    this._ensureAuthenticated();

    const formData = new FormData();
    const processedFiles: string[] = [];

    if (files.length !== options.document_ids.length) {
      throw new Error("Each file must have a corresponding document ID.");
    }

    const processFile = (
      file: File | { path: string; name: string },
      index: number,
    ) => {
      if ("path" in file) {
        if (typeof window === "undefined") {
          formData.append("files", fs.createReadStream(file.path), file.name);
          processedFiles.push(file.name);
        } else {
          console.warn(
            "File path provided in browser environment. This is not supported.",
          );
        }
      } else {
        formData.append("files", file);
        processedFiles.push(file.name);
      }
    };

    files.forEach(processFile);

    const data: Record<string, string | undefined> = {
      document_ids: JSON.stringify(options.document_ids.map(String)),
      metadatas: options.metadatas
        ? JSON.stringify(options.metadatas)
        : undefined,
      ingestion_config: options.ingestion_config
        ? JSON.stringify(options.ingestion_config)
        : undefined,
      collection_ids: options.collection_ids
        ? JSON.stringify(options.collection_ids)
        : undefined,
      run_with_orchestration:
        options.run_with_orchestration != undefined
          ? String(options.run_with_orchestration)
          : undefined,
    };

    Object.entries(data).forEach(([key, value]) => {
      if (value !== undefined) {
        formData.append(key, value);
      }
    });

    formData.append("file_names", JSON.stringify(processedFiles));

    return await this._makeRequest("POST", "update_files", {
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
   *
   * @param chunks
   * @param documentId
   * @param metadata
   * @param run_with_orchestration
   * @deprecated use `client.chunks.create` instead.
   * @returns
   */
  @feature("ingestChunks")
  async ingestChunks(
    chunks: RawChunk[],
    documentId?: string,
    metadata?: Record<string, any>,
    run_with_orchestration?: boolean,
    collection_ids?: string[],
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    let inputData: Record<string, any> = {
      chunks: chunks,
      document_id: documentId,
      metadata: metadata,
      collection_ids: collection_ids,
      run_with_orchestration: run_with_orchestration,
    };

    return await this._makeRequest("POST", "ingest_chunks", {
      data: inputData,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  /**
   * Update the content of an existing chunk.
   *
   * @param documentId - The ID of the document containing the chunk.
   * @param extractionId - The ID of the chunk to update.
   * @param text - The new text content of the chunk.
   * @param metadata - Optional metadata dictionary for the chunk.
   * @param runWithOrchestration - Whether to run the update through orchestration.
   * @returns Update results containing processed, failed, and skipped documents.
   * @deprecated Use `client.chunks.update` instead.
   */
  @feature("updateChunk")
  async updateChunk(
    documentId: string,
    extractionId: string,
    text: string,
    metadata?: Record<string, any>,
    runWithOrchestration?: boolean,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const data: Record<string, any> = {
      text,
      metadata,
      run_with_orchestration: runWithOrchestration,
    };

    Object.keys(data).forEach(
      (key) => data[key] === undefined && delete data[key],
    );

    return await this._makeRequest(
      "PUT",
      `update_chunk/${documentId}/${extractionId}`,
      {
        data,
      },
    );
  }

  /**
   * Create a vector index for similarity search.
   * @param options The options for creating the vector index
   * @returns Promise resolving to the creation response
   * @deprecated Use `client.indices.create` instead.
   */
  @feature("createVectorIndex")
  async createVectorIndex(options: {
    tableName: string;
    indexMethod: "hnsw" | "ivfflat" | "auto";
    indexMeasure: "cosine_distance" | "l2_distance" | "max_inner_product";
    indexArguments?: {
      m?: number; // HNSW: Number of connections per element
      ef_construction?: number; // HNSW: Size of dynamic candidate list
      n_lists?: number; // IVFFlat: Number of clusters/inverted lists
    };
    indexName?: string;
    concurrently?: boolean;
  }): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const data = {
      table_name: options.tableName,
      index_method: options.indexMethod,
      index_measure: options.indexMeasure,
      index_arguments: options.indexArguments,
      index_name: options.indexName,
      concurrently: options.concurrently ?? true,
    };

    return await this._makeRequest("POST", "create_vector_index", {
      data,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  /**
   * List existing vector indices for a table.
   * @param options The options for listing vector indices
   * @returns Promise resolving to the list of indices
   * @deprecated Use `client.indices.list` instead.
   */
  @feature("listVectorIndices")
  async listVectorIndices(options: {
    tableName?: string;
  }): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const params: Record<string, string> = {};
    if (options.tableName) {
      params.table_name = options.tableName;
    }

    return await this._makeRequest("GET", "list_vector_indices", { params });
  }

  /**
   * Delete a vector index from a table.
   * @param options The options for deleting the vector index
   * @returns Promise resolving to the deletion response
   * @deprecated Use `client.indices.delete` instead.
   */
  @feature("deleteVectorIndex")
  async deleteVectorIndex(options: {
    indexName: string;
    tableName?: string;
    concurrently?: boolean;
  }): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const data = {
      index_name: options.indexName,
      table_name: options.tableName,
      concurrently: options.concurrently ?? true,
    };

    return await this._makeRequest("DELETE", "delete_vector_index", {
      data,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  // -----------------------------------------------------------------------------
  //
  // Management
  //
  // -----------------------------------------------------------------------------

  /**
   * Check the health of the R2R deployment.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.system.health` instead.
   */
  async health(): Promise<any> {
    return await this._makeRequest("GET", "health");
  }

  /**
   * Get statistics about the server, including the start time, uptime, CPU usage, and memory usage.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.system.status` instead.
   */
  @feature("serverStats")
  async serverStats(): Promise<any> {
    this._ensureAuthenticated();
    return await this._makeRequest("GET", "server_stats");
  }

  /**
   * Update a prompt in the database.
   * @param name The name of the prompt to update.
   * @param template The new template for the prompt.
   * @param input_types The new input types for the prompt.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.prompts.update` instead.
   */
  @feature("updatePrompt")
  async updatePrompt(
    name: string = "default_system",
    template?: string,
    input_types?: Record<string, string>,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const data: Record<string, any> = { name };
    if (template !== undefined) {
      data.template = template;
    }
    if (input_types !== undefined) {
      data.input_types = input_types;
    }

    return await this._makeRequest("POST", "update_prompt", {
      data,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  /**
   * Add a new prompt to the system.
   * @returns A promise that resolves to the response from the server.
   * @param name The name of the prompt.
   * @param template The template for the prompt.
   * @param input_types The input types for the prompt.
   * @deprecated Use `client.prompts.create` instead.
   */
  @feature("addPrompt")
  async addPrompt(
    name: string,
    template: string,
    input_types: Record<string, string>,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const data: Record<string, any> = { name, template, input_types };

    return await this._makeRequest("POST", "add_prompt", {
      data,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  /**
   * Get a prompt from the system.
   * @param name The name of the prompt to retrieve.
   * @param inputs Inputs for the prompt.
   * @param prompt_override Override for the prompt template.
   * @deprecated Use `client.prompts.retrieve` instead.
   * @returns
   */
  @feature("getPrompt")
  async getPrompt(
    name: string,
    inputs?: Record<string, any>,
    prompt_override?: string,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const params: Record<string, any> = {};
    if (inputs) {
      params["inputs"] = JSON.stringify(inputs);
    }
    if (prompt_override) {
      params["prompt_override"] = prompt_override;
    }

    return await this._makeRequest("GET", `get_prompt/${name}`, { params });
  }

  /**
   * Get all prompts from the system.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.prompts.list` instead.
   */
  @feature("getAllPrompts")
  async getAllPrompts(): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return await this._makeRequest("GET", "get_all_prompts");
  }

  /**
   * Delete a prompt from the system.
   * @param prompt_name The name of the prompt to delete.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.prompts.delete` instead.
   */
  @feature("deletePrompt")
  async deletePrompt(prompt_name: string): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return await this._makeRequest("DELETE", `delete_prompt/${prompt_name}`);
  }

  /**
   * Get analytics data from the server.
   * @param filter_criteria The filter criteria to use.
   * @param analysis_types The types of analysis to perform.
   * @returns A promise that resolves to the response from the server.
   * @deprecated This method is deprecated. New, improved analytics features will be added in a future release.
   */
  @feature("analytics")
  async analytics(
    filter_criteria?: Record<string, any> | string,
    analysis_types?: Record<string, any> | string,
  ): Promise<any> {
    this._ensureAuthenticated();

    const params: Record<string, string> = {};

    if (filter_criteria) {
      params.filter_criteria =
        typeof filter_criteria === "string"
          ? filter_criteria
          : JSON.stringify(filter_criteria);
    }

    if (analysis_types) {
      params.analysis_types =
        typeof analysis_types === "string"
          ? analysis_types
          : JSON.stringify(analysis_types);
    }

    return this._makeRequest("GET", "analytics", { params });
  }

  /**
   * Get logs from the server.
   * @param run_type_filter The run type to filter by.
   * @param max_runs Specifies the maximum number of runs to return. Values outside the range of 1 to 1000 will be adjusted to the nearest valid value with a default of 100.
   * @returns
   * @deprecated Use `client.system.logs` instead.
   */
  @feature("logs")
  async logs(run_type_filter?: string, max_runs?: number): Promise<any> {
    this._ensureAuthenticated();

    const params: Record<string, string | number> = {};

    if (run_type_filter !== undefined) {
      params.run_type_filter = run_type_filter;
    }

    if (max_runs !== undefined) {
      params.max_runs = max_runs;
    }

    return this._makeRequest("GET", "logs", { params });
  }

  /**
   * Get the configuration settings for the app.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.system.settings` instead.
   */
  @feature("appSettings")
  async appSettings(): Promise<any> {
    this._ensureAuthenticated();

    return this._makeRequest("GET", "app_settings");
  }

  /**
   * An overview of the users in the R2R deployment.
   * @param user_ids List of user IDs to get an overview for.
   * * @param offset The offset to start listing users from.
   * @param limit The maximum number of users to return.
   * @returns
   * @deprecated Use `client.users.list` instead.
   */
  @feature("usersOverview")
  async usersOverview(
    user_ids?: string[],
    offset?: number,
    limit?: number,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    let params: Record<string, any> = {};
    if (user_ids && user_ids.length > 0) {
      params.user_ids = user_ids;
    }
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }

    if (user_ids && user_ids.length > 0) {
      params.user_ids = user_ids;
    }

    return this._makeRequest("GET", "users_overview", { params });
  }

  /**
   * Delete data from the database given a set of filters.
   * @param filters The filters to delete by.
   * @returns The results of the deletion.
   * @deprecated Use `client.<object>.delete` instead for the specific object you want to delete.
   */
  @feature("delete")
  async delete(filters: { [key: string]: any }): Promise<any> {
    this._ensureAuthenticated();

    const params = {
      filters: JSON.stringify(filters),
    };

    return this._makeRequest("DELETE", "delete", { params }) || { results: {} };
  }

  /**
   * Download the raw file associated with a document.
   * @param documentId The ID of the document to retrieve.
   * @returns A promise that resolves to a Blob representing the PDF.
   * @deprecated Use `client.documents.download` instead.
   */
  @feature("downloadFile")
  async downloadFile(documentId: string): Promise<Blob> {
    return await this._makeRequest<Blob>("GET", `download_file/${documentId}`, {
      responseType: "blob",
    });
  }

  /**
   * Get an overview of documents in the R2R deployment.
   * @param document_ids List of document IDs to get an overview for.
   * @param offset The offset to start listing documents from.
   * @param limit The maximum number of documents to return.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.documents.list` instead.
   */
  @feature("documentsOverview")
  async documentsOverview(
    document_ids?: string[],
    offset?: number,
    limit?: number,
  ): Promise<any> {
    this._ensureAuthenticated();

    let params: Record<string, any> = {};
    if (document_ids && document_ids.length > 0) {
      params.document_ids = document_ids;
    }
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }

    return this._makeRequest("GET", "documents_overview", { params });
  }

  /**
   * Get the chunks for a document.
   * @param document_id The ID of the document to get the chunks for.
   * @returns A promise that resolves to the response from the server.
   * @deprecated Use `client.documents.listChunks` instead.
   */
  @feature("documentChunks")
  async documentChunks(
    document_id: string,
    offset?: number,
    limit?: number,
  ): Promise<any> {
    this._ensureAuthenticated();

    const params: Record<string, number> = {};
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }

    return this._makeRequest("GET", `document_chunks/${document_id}`, {
      headers: {
        "Content-Type": "application/json",
      },
      params,
    });
  }

  /**
   * Get an overview of existing collections.
   * @param collectionIds List of collection IDs to get an overview for.
   * @param limit The maximum number of collections to return.
   * @param offset The offset to start listing collections from.
   * @deprecated use `client.collections.list` instead
   * @returns
   */
  @feature("collectionsOverview")
  async collectionsOverview(
    collectionIds?: string[],
    offset?: number,
    limit?: number,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const params: Record<string, string | number | string[]> = {};
    if (collectionIds && collectionIds.length > 0) {
      params.collection_ids = collectionIds;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }
    if (offset !== undefined) {
      params.offset = offset;
    }

    return this._makeRequest("GET", "collections_overview", { params });
  }

  /**
   * Create a new collection.
   * @param name The name of the collection.
   * @param description The description of the collection.
   * @returns
   * @deprecated use `client.collections.create` instead
   */
  @feature("createCollection")
  async createCollection(
    name: string,
    description?: string,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const data: { name: string; description?: string } = { name };
    if (description !== undefined) {
      data.description = description;
    }

    return this._makeRequest("POST", "create_collection", { data });
  }

  /**
   * Get a collection by its ID.
   * @param collectionId The ID of the collection to get.
   * @returns A promise that resolves to the response from the server.
   * @deprecated use `client.collections.retrieve` instead
   */
  @feature("getCollection")
  async getCollection(collectionId: string): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest(
      "GET",
      `get_collection/${encodeURIComponent(collectionId)}`,
    );
  }

  /**
   * Updates the name and description of a collection.
   * @param collectionId The ID of the collection to update.
   * @param name The new name for the collection.
   * @param description The new description of the collection.
   * @returns A promise that resolves to the response from the server.
   * @deprecated use `client.collections.update` instead
   */
  @feature("updateCollection")
  async updateCollection(
    collectionId: string,
    name?: string,
    description?: string,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const data: { collection_id: string; name?: string; description?: string } =
      {
        collection_id: collectionId,
      };
    if (name !== undefined) {
      data.name = name;
    }
    if (description !== undefined) {
      data.description = description;
    }

    return this._makeRequest("PUT", "update_collection", { data });
  }

  /**
   * Delete a collection by its ID.
   * @param collectionId The ID of the collection to delete.
   * @returns A promise that resolves to the response from the server.
   * @deprecated use `client.collections.delete` instead
   */
  @feature("deleteCollection")
  async deleteCollection(collectionId: string): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest(
      "DELETE",
      `delete_collection/${encodeURIComponent(collectionId)}`,
    );
  }

  /**
   * List all collections in the R2R deployment.
   * @param offset The offset to start listing collections from.
   * @param limit The maximum numberof collections to return.
   * @returns
   * @deprecated use `client.collections.list` instead
   */
  @feature("listCollections")
  async listCollections(
    offset?: number,
    limit?: number,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const params: Record<string, number> = {};
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }

    return this._makeRequest("GET", "list_collections", { params });
  }

  /**
   * Add a user to a collection.
   * @param userId The ID of the user to add.
   * @param collectionId The ID of the collection to add the user to.
   * @returns A promise that resolves to the response from the server.
   * @deprecated use `client.collections.addUser` instead
   */
  @feature("addUserToCollection")
  async addUserToCollection(
    userId: string,
    collectionId: string,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest("POST", "add_user_to_collection", {
      data: { user_id: userId, collection_id: collectionId },
    });
  }

  /**
   * Remove a user from a collection.
   * @param userId The ID of the user to remove.
   * @param collectionId The ID of the collection to remove the user from.
   * @returns
   * @deprecated use `client.collections.removeUser` instead
   */
  @feature("removeUserFromCollection")
  async removeUserFromCollection(
    userId: string,
    collectionId: string,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest("POST", "remove_user_from_collection", {
      data: { user_id: userId, collection_id: collectionId },
    });
  }

  /**
   * Get all users in a collection.
   * @param collectionId The ID of the collection to get users for.
   * @param offset The offset to start listing users from.
   * @param limit The maximum number of users to return.
   * @returns A promise that resolves to the response from the server.
   * @deprecated use `client.collections.listUsers` instead
   */
  @feature("getUsersInCollection")
  async getUsersInCollection(
    collectionId: string,
    offset?: number,
    limit?: number,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const params: Record<string, string | number> = {};
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }

    return this._makeRequest(
      "GET",
      `get_users_in_collection/${encodeURIComponent(collectionId)}`,
      { params },
    );
  }

  /**
   * Get all collections that a user is a member of.
   * @param userId The ID of the user to get collections for.
   * @returns A promise that resolves to the response from the server.
   * @deprecated use `client.users.listCollections` instead
   */
  @feature("getCollectionsForUser")
  async getCollectionsForUser(
    userId: string,
    offset?: number,
    limit?: number,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const params: Record<string, string | number> = {};
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }

    return this._makeRequest(
      "GET",
      `user_collections/${encodeURIComponent(userId)}`,
      { params },
    );
  }

  /**
   * Assign a document to a collection.
   * @param document_id The ID of the document to assign.
   * @param collection_id The ID of the collection to assign the document to.
   * @returns
   * @deprecated use `client.collections.addDocument` instead
   */
  @feature("assignDocumentToCollection")
  async assignDocumentToCollection(
    document_id: string,
    collection_id: string,
  ): Promise<any> {
    this._ensureAuthenticated();

    return this._makeRequest("POST", "assign_document_to_collection", {
      data: { document_id, collection_id },
    });
  }

  /**
   * Remove a document from a collection.
   * @param document_id The ID of the document to remove.
   * @param collection_id The ID of the collection to remove the document from.
   * @returns A promise that resolves to the response from the server.
   * @deprecated use `client.collections.removeDocument` instead
   */
  @feature("removeDocumentFromCollection")
  async removeDocumentFromCollection(
    document_id: string,
    collection_id: string,
  ): Promise<any> {
    this._ensureAuthenticated();

    return this._makeRequest("POST", "remove_document_from_collection", {
      data: { document_id, collection_id },
    });
  }

  /**
   * Get all collections that a document is assigned to.
   * @param documentId The ID of the document to get collections for.
   * @returns
   * @deprecated use `client.collections.listDocuments` instead
   */
  @feature("getDocumentCollections")
  async getDocumentCollections(
    documentId: string,
    offset?: number,
    limit?: number,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const params: Record<string, string | number> = {};
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }

    return this._makeRequest(
      "GET",
      `document_collections/${encodeURIComponent(documentId)}`,
      { params },
    );
  }

  /**
   * Get all documents in a collection.
   * @param collectionId The ID of the collection to get documents for.
   * @param offset The offset to start listing documents from.
   * @param limit The maximum number of documents to return.
   * @returns A promise that resolves to the response from the server.
   * @deprecated use `client.collections.listDocuments` instead
   */
  @feature("getDocumentsInCollection")
  async getDocumentsInCollection(
    collectionId: string,
    offset?: number,
    limit?: number,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const params: Record<string, number> = {};
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }

    return this._makeRequest(
      "GET",
      `collection/${encodeURIComponent(collectionId)}/documents`,
      { params },
    );
  }

  /**
   * Get an overview of existing conversations.
   * @param limit The maximum number of conversations to return.
   * @param offset The offset to start listing conversations from.
   * @deprecated use `client.conversations.list` instead
   * @returns
   */
  @feature("conversationsOverview")
  async conversationsOverview(
    conversation_ids?: string[],
    offset?: number,
    limit?: number,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    let params: Record<string, any> = {};
    if (conversation_ids && conversation_ids.length > 0) {
      params.conversation_ids = conversation_ids;
    }
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }

    return this._makeRequest("GET", "conversations_overview", { params });
  }

  /**
   * Get a conversation by its ID.
   * @param conversationId The ID of the conversation to get.
   * @param branchId The ID of the branch (optional).
   * @deprecated use `client.conversations.retrieve` instead
   * @returns A promise that resolves to the response from the server.
   */
  @feature("getConversation")
  async getConversation(conversationId: string): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest("GET", `get_conversation/${conversationId}`);
  }

  /**
   * Create a new conversation.
   * @deprecated use `client.conversations.create` instead
   * @returns A promise that resolves to the response from the server.
   */
  @feature("createConversation")
  async createConversation(): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest("POST", "create_conversation");
  }

  /**
   * Add a message to an existing conversation.
   * @param conversationId
   * @param message
   * @deprecated use `client.conversations.addMessage` instead
   * @returns
   */
  @feature("addMessage")
  async addMessage(
    conversationId: string,
    message: Message,
    parent_id?: string,
    metadata?: Record<string, any>,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    const data: any = { message }; // Nest message under 'message' key
    if (parent_id !== undefined) {
      data.parent_id = parent_id;
    }
    if (metadata !== undefined) {
      data.metadata = metadata;
    }
    return this._makeRequest("POST", `add_message/${conversationId}`, { data });
  }

  /**
   * Update a message in an existing conversation.
   * @param message_id The ID of the message to update.
   * @param message The updated message.
   * @deprecated use `client.conversations.updateMessage` instead
   * @returns A promise that resolves to the response from the server.
   */
  @feature("updateMessage")
  async updateMessage(
    message_id: string,
    message: Message,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest("PUT", `update_message/${message_id}`, {
      data: message,
    });
  }

  /**
   * Update the metadata of a message in an existing conversation.
   * @param message_id The ID of the message to update.
   * @param metadata The updated metadata.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("updateMessageMetadata")
  async updateMessageMetadata(
    message_id: string,
    metadata: Record<string, any>,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest("PATCH", `messages/${message_id}/metadata`, {
      data: metadata,
    });
  }

  /**
   * Get an overview of branches in a conversation.
   * @param conversationId The ID of the conversation to get branches for.
   * @deprecated use `client.conversations.listBranches` instead
   * @returns A promise that resolves to the response from the server.
   */
  @feature("branchesOverview")
  async branchesOverview(conversationId: string): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest("GET", `branches_overview/${conversationId}`);
  }

  // TODO: Publish these methods once more testing is done
  // /**
  //  * Get the next branch in a conversation.
  //  * @param branchId The ID of the branch to get the next branch for.
  //  * @returns A promise that resolves to the response from the server.
  //  */
  // @feature("getNextBranch")
  // async getNextBranch(branchId: string): Promise<Record<string, any>> {
  //   this._ensureAuthenticated();
  //   return this._makeRequest("GET", `get_next_branch/${branchId}`);
  // }

  // /**
  //  * Get the previous branch in a conversation.
  //  * @param branchId The ID of the branch to get the previous branch for.
  //  * @returns A promise that resolves to the response from the server.
  //  */
  // @feature("getPreviousBranch")
  // async getPreviousBranch(branchId: string): Promise<Record<string, any>> {
  //   this._ensureAuthenticated();
  //   return this._makeRequest("GET", `get_previous_branch/${branchId}`);
  // }

  // /**
  //  * Branch at a specific message in a conversation.
  //  * @param conversationId The ID of the conversation to branch.
  //  * @param message_id The ID of the message to branch at.
  //  * @returns A promise that resolves to the response from the server.
  //  */
  // @feature("branchAtMessage")
  // async branchAtMessage(
  //   conversationId: string,
  //   message_id: string,
  // ): Promise<Record<string, any>> {
  //   this._ensureAuthenticated();
  //   return this._makeRequest(
  //     "POST",
  //     `branch_at_message/${conversationId}/${message_id}`,
  //   );
  // }

  /**
   * Delete a conversation by its ID.
   * @param conversationId The ID of the conversation to delete.
   * @deprecated use `client.conversations.delete` instead
   * @returns A promise that resolves to the response from the server.
   */
  @feature("deleteConversation")
  async deleteConversation(
    conversationId: string,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest("DELETE", `delete_conversation/${conversationId}`);
  }

  // -----------------------------------------------------------------------------
  //
  // Knowledge Graphs
  //
  // -----------------------------------------------------------------------------

  /**
   * Create a graph from the given settings.
   * @returns A promise that resolves to the response from the server.
   *
   * @param collection_id The ID of the collection to create the graph for.
   * @param run_type The type of run to perform.
   * @param graph_creation_settings Settings for the graph creation process.
   */
  @feature("createGraph")
  async createGraph(
    collection_id?: string,
    run_type?: KGRunType,
    graph_creation_settings?: Record<string, any>,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const json_data: Record<string, any> = {
      collection_id,
      run_type,
      graph_creation_settings,
    };

    Object.keys(json_data).forEach(
      (key) => json_data[key] === undefined && delete json_data[key],
    );

    return await this._makeRequest("POST", "create_graph", { data: json_data });
  }
  /**
   * Perform graph enrichment over the entire graph.
   * @returns A promise that resolves to the response from the server.
   *
   * @param collection_id The ID of the collection to enrich the graph for.
   * @param run_type The type of run to perform.
   * @param graph_enrichment_settings Settings for the graph enrichment process.
   */
  @feature("enrichGraph")
  async enrichGraph(
    collection_id?: string,
    run_type?: KGRunType,
    graph_enrichment_settings?: Record<string, any>,
  ): Promise<any> {
    this._ensureAuthenticated();

    const json_data: Record<string, any> = {
      collection_id,
      run_type,
      graph_enrichment_settings,
    };

    Object.keys(json_data).forEach(
      (key) => json_data[key] === undefined && delete json_data[key],
    );

    return await this._makeRequest("POST", "enrich_graph", { data: json_data });
  }

  /**
   * Retrieve entities from the knowledge graph.
   * @returns A promise that resolves to the response from the server.
   * @param collection_id The ID of the collection to retrieve entities for.
   * @param offset The offset for pagination.
   * @param limit The limit for pagination.
   * @param entity_level The level of entity to filter by.
   * @param entity_ids Entity IDs to filter by.
   * @returns
   */
  @feature("getEntities")
  async getEntities(
    collection_id?: string,
    offset?: number,
    limit?: number,
    entity_level?: string,
    entity_ids?: string[],
  ): Promise<any> {
    this._ensureAuthenticated();

    const params: Record<string, any> = {};
    if (collection_id !== undefined) {
      params.collection_id = collection_id;
    }
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }
    if (entity_level !== undefined) {
      params.entity_level = entity_level;
    }
    if (entity_ids !== undefined) {
      params.entity_ids = entity_ids;
    }

    return this._makeRequest("GET", `entities`, { params });
  }

  /**
   * Retrieve relationships from the knowledge graph.
   * @returns A promise that resolves to the response from the server.
   * @param collection_id The ID of the collection to retrieve entities for.
   * @param offset The offset for pagination.
   * @param limit The limit for pagination.
   * @param entity_level The level of entity to filter by.
   * @param relationship_ids Relationship IDs to filter by.
   */
  @feature("getTriples")
  async getTriples(
    collection_id?: string,
    offset?: number,
    limit?: number,
    entity_level?: string,
    relationship_ids?: string[],
  ): Promise<any> {
    this._ensureAuthenticated();

    const params: Record<string, any> = {};
    if (collection_id !== undefined) {
      params.collection_id = collection_id;
    }
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }
    if (entity_level !== undefined) {
      params.entity_level = entity_level;
    }
    if (relationship_ids !== undefined) {
      params.entity_ids = relationship_ids;
    }

    return this._makeRequest("GET", `triples`, { params });
  }

  /**
   * Retrieve communities from the knowledge graph.
   * @param collection_id The ID of the collection to retrieve entities for.
   * @param offset The offset for pagination.
   * @param limit The limit for pagination.
   * @param levels Levels to filter by.
   * @param community_ids Community numbers to filter by.
   * @returns
   */
  @feature("getCommunities")
  async getCommunities(
    collection_id?: string,
    offset?: number,
    limit?: number,
    levels?: number,
    community_ids?: number[],
  ): Promise<any> {
    this._ensureAuthenticated();

    const params: Record<string, any> = {};
    if (collection_id !== undefined) {
      params.collection_id = collection_id;
    }
    if (offset !== undefined) {
      params.offset = offset;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }
    if (levels !== undefined) {
      params.levels = levels;
    }
    if (community_ids !== undefined) {
      params.community_ids = community_ids;
    }

    return this._makeRequest("GET", `communities`, { params });
  }

  @feature("getTunedPrompt")
  async getTunedPrompt(
    prompt_name: string,
    collection_id?: string,
    documents_offset?: number,
    documents_limit?: number,
    chunk_offset?: number,
    chunk_limit?: number,
  ): Promise<any> {
    this._ensureAuthenticated();

    const params: Record<string, any> = { prompt_name };
    if (collection_id !== undefined) {
      params.collection_id = collection_id;
    }
    if (documents_offset !== undefined) {
      params.documents_offset = documents_offset;
    }
    if (documents_limit !== undefined) {
      params.documents_limit = documents_limit;
    }
    if (chunk_offset !== undefined) {
      params.chunk_offset = chunk_offset;
    }
    if (chunk_limit !== undefined) {
      params.chunk_limit = chunk_limit;
    }

    return this._makeRequest("GET", `tuned_prompt`, { params });
  }

  @feature("deduplicateEntities")
  async deduplicateEntities(
    collections_id?: string,
    run_type?: KGRunType,
    deduplication_settings?:
      | KGEntityDeduplicationSettings
      | Record<string, any>,
  ): Promise<any> {
    this._ensureAuthenticated();

    const json_data: Record<string, any> = {
      collections_id,
      run_type,
      deduplication_settings,
    };

    Object.keys(json_data).forEach(
      (key) => json_data[key] === undefined && delete json_data[key],
    );

    return await this._makeRequest("POST", "deduplicate_entities", {
      data: json_data,
    });
  }

  @feature("deleteGraphForCollection")
  async deleteGraphForCollection(
    collection_id: string,
    cascade: boolean = false,
  ): Promise<any> {
    this._ensureAuthenticated();

    const json_data: Record<string, any> = {
      collection_id,
      cascade,
    };

    return await this._makeRequest("DELETE", `delete_graph`, {
      data: json_data,
    });
  }

  // -----------------------------------------------------------------------------
  //
  // Retrieval
  //
  // -----------------------------------------------------------------------------

  /**
   * Search over documents.
   * @param query The query to search for.
   * @param vector_search_settings Settings for the document search.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("searchDocuments")
  async searchDocuments(
    query: string,
    vector_search_settings?: Record<string, any>,
  ): Promise<any> {
    this._ensureAuthenticated();
    const json_data: Record<string, any> = {
      query,
      vector_search_settings,
    };

    Object.keys(json_data).forEach(
      (key) => json_data[key] === undefined && delete json_data[key],
    );

    return await this._makeRequest("POST", "search_documents", {
      data: json_data,
    });
  }

  /**
   * Conduct a vector and/or KG search.
   * @param query The query to search for.
   * @param vector_search_settings Vector search settings.
   * @param graph_search_settings KG search settings.
   * @deprecated use `client.retrieval.search` instead
   * @returns
   */
  @feature("search")
  async search(
    query: string,
    vector_search_settings?: Record<string, any>,
    graph_search_settings?: Record<string, any>,
  ): Promise<any> {
    this._ensureAuthenticated();

    const json_data: Record<string, any> = {
      query,
      vector_search_settings,
      graph_search_settings,
    };

    Object.keys(json_data).forEach(
      (key) => json_data[key] === undefined && delete json_data[key],
    );

    return await this._makeRequest("POST", "search", { data: json_data });
  }

  /**
   * Conducts a Retrieval Augmented Generation (RAG) search with the given query.
   * @param query The query to search for.
   * @param vector_search_settings Vector search settings.
   * @param graph_search_settings KG search settings.
   * @param rag_generation_config RAG generation configuration.
   * @param task_prompt_override Task prompt override.
   * @param include_title_if_available Include title if available.
   * @deprecated use `client.retrieval.search` instead
   * @returns A promise that resolves to the response from the server.
   */
  @feature("rag")
  async rag(
    query: string,
    vector_search_settings?: Record<string, any>,
    graph_search_settings?: Record<string, any>,
    rag_generation_config?: Record<string, any>,
    task_prompt_override?: string,
    include_title_if_available?: boolean,
  ): Promise<any | AsyncGenerator<string, void, unknown>> {
    this._ensureAuthenticated();

    const json_data: Record<string, any> = {
      query,
      vector_search_settings,
      graph_search_settings,
      rag_generation_config,
      task_prompt_override,
      include_title_if_available,
    };

    Object.keys(json_data).forEach(
      (key) => json_data[key] === undefined && delete json_data[key],
    );

    if (rag_generation_config && rag_generation_config.stream) {
      return this.streamRag(json_data);
    } else {
      return await this._makeRequest("POST", "rag", { data: json_data });
    }
  }

  // TODO: can we remove this and pull this into rag?
  @feature("streamingRag")
  private async streamRag(
    rag_data: Record<string, any>,
  ): Promise<ReadableStream<Uint8Array>> {
    this._ensureAuthenticated();

    return this._makeRequest<ReadableStream<Uint8Array>>("POST", "rag", {
      data: rag_data,
      headers: {
        "Content-Type": "application/json",
      },
      responseType: "stream",
    });
  }

  /**
   * Performs a single turn in a conversation with a RAG agent.
   * @param messages The messages to send to the agent.
   * @param rag_generation_config RAG generation configuration.
   * @param vector_search_settings Vector search settings.
   * @param graph_search_settings KG search settings.
   * @param task_prompt_override Task prompt override.
   * @param include_title_if_available Include title if available.
   * @param conversation_id The ID of the conversation, if not a new conversation.
   * @returns A promise that resolves to the response from the server.
   * @deprecated use `client.retrieval.agent` instead
   */
  @feature("agent")
  async agent(
    messages: Message[],
    rag_generation_config?: Record<string, any>,
    vector_search_settings?: Record<string, any>,
    graph_search_settings?: Record<string, any>,
    task_prompt_override?: string,
    include_title_if_available?: boolean,
    conversation_id?: string,
  ): Promise<any | AsyncGenerator<string, void, unknown>> {
    this._ensureAuthenticated();

    const json_data: Record<string, any> = {
      messages,
      vector_search_settings,
      graph_search_settings,
      rag_generation_config,
      task_prompt_override,
      include_title_if_available,
      conversation_id,
    };

    Object.keys(json_data).forEach(
      (key) => json_data[key] === undefined && delete json_data[key],
    );

    if (rag_generation_config && rag_generation_config.stream) {
      return this.streamAgent(json_data);
    } else {
      return await this._makeRequest("POST", "agent", { data: json_data });
    }
  }

  // TODO: can we remove this and pull this into agent?
  @feature("streamingAgent")
  private async streamAgent(
    agent_data: Record<string, any>,
  ): Promise<ReadableStream<Uint8Array>> {
    this._ensureAuthenticated();

    return this._makeRequest<ReadableStream<Uint8Array>>("POST", "agent", {
      data: agent_data,
      headers: {
        "Content-Type": "application/json",
      },
      responseType: "stream",
    });
  }
}

export default r2rClient;
