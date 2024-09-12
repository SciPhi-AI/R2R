import axios, {
  AxiosInstance,
  Method,
  AxiosResponse,
  AxiosRequestConfig,
} from "axios";
import FormData from "form-data";

let fs: any;
if (typeof window === "undefined") {
  import("fs").then((module) => {
    fs = module;
  });
}

import { feature, featureGenerator, initializeTelemetry } from "./feature";
import {
  LoginResponse,
  TokenInfo,
  Message,
  RefreshTokenResponse,
  VectorSearchSettings,
  KGSearchSettings,
  GenerationConfig,
} from "./models";

function handleRequestError(response: AxiosResponse): void {
  if (response.status < 400) {
    return;
  }

  let message: string;
  const errorContent = response.data;

  if (
    typeof errorContent === "object" &&
    errorContent !== null &&
    "detail" in errorContent
  ) {
    const { detail } = errorContent;
    if (typeof detail === "object" && detail !== null) {
      message = (detail as { message?: string }).message || response.statusText;
    } else {
      message = String(detail);
    }
  } else {
    message = String(errorContent);
  }

  throw new Error(`Status ${response.status}: ${message}`);
}

export class r2rClient {
  private axiosInstance: AxiosInstance;
  private baseUrl: string;
  private accessToken: string | null;
  private refreshToken: string | null;

  constructor(baseURL: string, prefix: string = "/v2") {
    this.baseUrl = `${baseURL}${prefix}`;
    this.accessToken = null;
    this.refreshToken = null;

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

    initializeTelemetry();
  }

  private async _makeRequest<T = any>(
    method: Method,
    endpoint: string,
    options: any = {},
  ): Promise<T> {
    const url = `${endpoint}`;
    const config: AxiosRequestConfig = {
      method,
      url,
      headers: { ...options.headers },
      params: options.params,
      ...options,
      responseType: options.responseType || "json",
    };

    config.headers = config.headers || {};

    if (options.params) {
      config.paramsSerializer = (params) => {
        return Object.entries(params)
          .map(([key, value]) => {
            if (Array.isArray(value)) {
              return value
                .map(
                  (v) => `${encodeURIComponent(key)}=${encodeURIComponent(v)}`,
                )
                .join("&");
            }
            return `${encodeURIComponent(key)}=${encodeURIComponent(String(value))}`;
          })
          .join("&");
      };
    }

    if (options.data) {
      if (typeof FormData !== "undefined" && options.data instanceof FormData) {
        config.data = options.data;
        delete config.headers["Content-Type"];
      } else if (typeof options.data === "object") {
        if (
          config.headers["Content-Type"] === "application/x-www-form-urlencoded"
        ) {
          config.data = Object.keys(options.data)
            .map(
              (key) =>
                `${encodeURIComponent(key)}=${encodeURIComponent(options.data[key])}`,
            )
            .join("&");
        } else {
          config.data = JSON.stringify(options.data);
          if (method !== "DELETE") {
            config.headers["Content-Type"] = "application/json";
          } else {
            config.headers["Content-Type"] = "application/json";
            config.data = JSON.stringify(options.data);
          }
        }
      } else {
        config.data = options.data;
      }
    }

    if (
      this.accessToken &&
      !["register", "login", "verify_email", "health"].includes(endpoint)
    ) {
      config.headers.Authorization = `Bearer ${this.accessToken}`;
    }

    if (options.responseType === "stream") {
      const fetchHeaders: Record<string, string> = {};
      Object.entries(config.headers).forEach(([key, value]) => {
        if (typeof value === "string") {
          fetchHeaders[key] = value;
        }
      });
      const response = await fetch(`${this.baseUrl}/${endpoint}`, {
        method,
        headers: fetchHeaders,
        body: config.data,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      return response.body as unknown as T;
    }

    try {
      const response = await this.axiosInstance.request(config);
      return options.returnFullResponse
        ? (response as any as T)
        : response.data;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        handleRequestError(error.response);
      }
      throw error;
    }
  }

  private _ensureAuthenticated(): void {
    // if (!this.accessToken) {
    //   throw new Error("Not authenticated. Please login first.");
    // }
  }

  async health(): Promise<any> {
    return await this._makeRequest("GET", "health");
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
   */
  @feature("verifyEmail")
  async verifyEmail(verification_code: string): Promise<any> {
    return await this._makeRequest("POST", "verify_email", {
      data: { verification_code },
    });
  }

  /**
   * Attempts to log in a user with the given email and password.
   * @param email The email of the user to log in.
   * @param password The password of the user to log in.
   * @returns A promise that resolves to the response from the server containing the access and refresh tokens.
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
   * Logs out the currently authenticated user.
   * @returns A promise that resolves to the response from the server.
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
   */
  @feature("updateUser")
  async updateUser(
    email?: string,
    name?: string,
    bio?: string,
    profilePicture?: string,
  ): Promise<any> {
    this._ensureAuthenticated();
    return await this._makeRequest("PUT", "user", {
      data: {
        email,
        name,
        bio,
        profile_picture: profilePicture,
      },
    });
  }

  /**
   * Refreshes the access token for the currently authenticated user.
   * @returns A promise that resolves to the response from the server containing the new access and refresh tokens.
   */
  async refreshAccessToken(): Promise<RefreshTokenResponse> {
    if (!this.refreshToken) {
      throw new Error("No refresh token available. Please login again.");
    }

    const response = await this._makeRequest<RefreshTokenResponse>(
      "POST",
      "refresh_access_token",
      { data: { refresh_token: this.refreshToken } },
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
   */
  @feature("requestPasswordReset")
  async requestPasswordReset(email: string): Promise<any> {
    return this._makeRequest("POST", "request_password_reset", {
      data: { email },
    });
  }

  /**
   * Confirms a password reset for the user with the given reset token.
   * @param resetToken The reset token to confirm the password reset with.
   * @param newPassword The new password to set for the user.
   * @returns A promise that resolves to the response from the server.
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
   */
  @feature("deleteUser")
  async deleteUser(userId: string, password?: string): Promise<any> {
    this._ensureAuthenticated();

    const data: Record<string, any> = { user_id: userId };

    if (password) {
      data.password = password;
    }

    return await this._makeRequest("DELETE", "user", { data });
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
   */
  @feature("ingestFiles")
  async ingestFiles(
    files: (string | File | { path: string; name: string })[],
    options: {
      metadatas?: Record<string, any>[];
      document_ids?: string[];
      user_ids?: (string | null)[];
      chunking_config?: Record<string, any>;
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
      chunking_config: options.chunking_config
        ? JSON.stringify(options.chunking_config)
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
   */
  @feature("updateFiles")
  async updateFiles(
    files: (File | { path: string; name: string })[],
    options: {
      document_ids: string[];
      metadatas?: Record<string, any>[];
      chunking_config?: Record<string, any>;
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
      chunking_config: options.chunking_config
        ? JSON.stringify(options.chunking_config)
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

  // -----------------------------------------------------------------------------
  //
  // Management
  //
  // -----------------------------------------------------------------------------

  /**
   * Get statistics about the server, including the start time, uptime, CPU usage, and memory usage.
   * @returns A promise that resolves to the response from the server.
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
   * Get analytics data from the server.
   * @param filter_criteria The filter criteria to use.
   * @param analysis_types The types of analysis to perform.
   * @returns A promise that resolves to the response from the server.
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
   */
  @feature("appSettings")
  async appSettings(): Promise<any> {
    this._ensureAuthenticated();

    return this._makeRequest("GET", "app_settings");
  }

  /**
   * Assign a score to a message from an LLM completion. The score should be a float between -1.0 and 1.0.
   * @param message_id The ID of the message to score.
   * @param score The score to assign to the message.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("scoreCompletion")
  async scoreCompletion(message_id: string, score: number): Promise<any> {
    this._ensureAuthenticated();

    const data = {
      message_id,
      score,
    };

    return this._makeRequest("POST", "score_completion", {
      data,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  /**
   * An overview of the users in the R2R deployment.
   * @param user_ids
   * @returns
   */
  @feature("usersOverview")
  async usersOverview(user_ids?: string[]): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const params: { user_ids?: string[] } = {};
    if (user_ids && user_ids.length > 0) {
      params.user_ids = user_ids;
    }

    return this._makeRequest("GET", "users_overview", { params });
  }

  /**
   * Delete data from the database given a set of filters.
   * @param filters The filters to delete by.
   * @returns
   */
  @feature("delete")
  async delete(filters: { [key: string]: string | string[] }): Promise<any> {
    this._ensureAuthenticated();

    const params = {
      filters: JSON.stringify(filters),
    };

    return this._makeRequest("DELETE", "delete", {
      params,
    });
  }

  /**
   * Get an overview of documents in the R2R deployment.
   * @param document_ids List of document IDs to get an overview for.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("documentsOverview")
  async documentsOverview(document_ids?: string[]): Promise<any> {
    this._ensureAuthenticated();

    let params: Record<string, string[]> = {};
    if (document_ids && document_ids.length > 0) {
      params.document_ids = document_ids;
    }

    return this._makeRequest("GET", "documents_overview", { params });
  }

  /**
   * Get the chunks for a document.
   * @param document_id The ID of the document to get the chunks for.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("documentChunks")
  async documentChunks(document_id: string): Promise<any> {
    this._ensureAuthenticated();

    return this._makeRequest("GET", `document_chunks/${document_id}`, {
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  /**
   * Inspect the knowledge graph associated with your R2R deployment.
   * @param limit The maximum number of nodes to return. Defaults to 100.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("inspectKnowledgeGraph")
  async inspectKnowledgeGraph(limit?: number): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const params: { limit?: number } = {};
    if (limit !== undefined) {
      params.limit = limit;
    }

    return this._makeRequest("GET", "inspect_knowledge_graph", { params });
  }

  /**
   * Get an overview of existing groups.
   * @param groupIds List of group IDs to get an overview for.
   * @param limit The maximum number of groups to return.
   * @param offset The offset to start listing groups from.
   * @returns
   */
  @feature("groupsOverview")
  async groupsOverview(
    groupIds?: string[],
    limit?: number,
    offset?: number,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const params: Record<string, string | number | string[]> = {};
    if (groupIds && groupIds.length > 0) {
      params.group_ids = groupIds;
    }
    if (limit !== undefined) {
      params.limit = limit;
    }
    if (offset !== undefined) {
      params.offset = offset;
    }

    return this._makeRequest("GET", "groups_overview", { params });
  }

  /**
   * Create a new group.
   * @param name The name of the group.
   * @param description The description of the group.
   * @returns
   */
  @feature("createGroup")
  async createGroup(
    name: string,
    description?: string,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const data: { name: string; description?: string } = { name };
    if (description !== undefined) {
      data.description = description;
    }

    return this._makeRequest("POST", "create_group", { data });
  }

  /**
   * Get a group by its ID.
   * @param groupId The ID of the group to get.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("getGroup")
  async getGroup(groupId: string): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest("GET", `get_group/${encodeURIComponent(groupId)}`);
  }

  /**
   * Updates the name and description of a group.
   * @param groupId The ID of the group to update.
   * @param name The new name for the group.
   * @param description The new description of the group.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("updateGroup")
  async updateGroup(
    groupId: string,
    name?: string,
    description?: string,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const data: { group_id: string; name?: string; description?: string } = {
      group_id: groupId,
    };
    if (name !== undefined) {
      data.name = name;
    }
    if (description !== undefined) {
      data.description = description;
    }

    return this._makeRequest("PUT", "update_group", { data });
  }

  /**
   * Delete a group by its ID.
   * @param groupId The ID of the group to delete.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("deleteGroup")
  async deleteGroup(groupId: string): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest(
      "DELETE",
      `delete_group/${encodeURIComponent(groupId)}`,
    );
  }

  /**
   * List all groups in the R2R deployment.
   * @param offset The offset to start listing groups from.
   * @param limit The maximum numberof groups to return.
   * @returns
   */
  @feature("listGroups")
  async listGroups(
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

    return this._makeRequest("GET", "list_groups", { params });
  }

  /**
   * Add a user to a group.
   * @param userId The ID of the user to add.
   * @param groupId The ID of the group to add the user to.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("addUserToGroup")
  async addUserToGroup(
    userId: string,
    groupId: string,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest("POST", "add_user_to_group", {
      data: { user_id: userId, group_id: groupId },
    });
  }

  /**
   * Remove a user from a group.
   * @param userId The ID of the user to remove.
   * @param groupId The ID of the group to remove the user from.
   * @returns
   */
  @feature("removeUserFromGroup")
  async removeUserFromGroup(
    userId: string,
    groupId: string,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest("POST", "remove_user_from_group", {
      data: { user_id: userId, group_id: groupId },
    });
  }

  /**
   * Get all users in a group.
   * @param groupId The ID of the group to get users for.
   * @param offset The offset to start listing users from.
   * @param limit The maximum number of users to return.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("getUsersInGroup")
  async getUsersInGroup(
    groupId: string,
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
      `get_users_in_group/${encodeURIComponent(groupId)}`,
      { params },
    );
  }

  /**
   * Get all groups that a user is a member of.
   * @param userId The ID of the user to get groups for.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("getGroupsForUser")
  async getGroupsForUser(userId: string): Promise<Record<string, any>> {
    this._ensureAuthenticated();
    return this._makeRequest(
      "GET",
      `get_groups_for_user/${encodeURIComponent(userId)}`,
    );
  }

  /**
   * Assign a document to a group.
   * @param document_id The ID of the document to assign.
   * @param group_id The ID of the group to assign the document to.
   * @returns
   */
  @feature("assignDocumentToGroup")
  async assignDocumentToGroup(
    document_id: string,
    group_id: string,
  ): Promise<any> {
    this._ensureAuthenticated();

    return this._makeRequest("POST", "assign_document_to_group", {
      data: { document_id, group_id },
    });
  }

  /**
   * Remove a document from a group.
   * @param document_id The ID of the document to remove.
   * @param group_id The ID of the group to remove the document from.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("removeDocumentFromGroup")
  async removeDocumentFromGroup(
    document_id: string,
    group_id: string,
  ): Promise<any> {
    this._ensureAuthenticated();

    return this._makeRequest("POST", "remove_document_from_group", {
      data: { document_id, group_id },
    });
  }

  /**
   * Get all groups that a document is assigned to.
   * @param documentId The ID of the document to get groups for.
   * @returns
   */
  @feature("getDocumentGroups")
  async getDocumentGroups(documentId: string): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    return this._makeRequest(
      "GET",
      `get_document_groups/${encodeURIComponent(documentId)}`,
    );
  }

  /**
   * Get all documents in a group.
   * @param groupId The ID of the group to get documents for.
   * @param offset The offset to start listing documents from.
   * @param limit The maximum number of documents to return.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("getDocumentsInGroup")
  async getDocumentsInGroup(
    groupId: string,
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
      `group/${encodeURIComponent(groupId)}/documents`,
      { params },
    );
  }

  // -----------------------------------------------------------------------------
  //
  // Restructure
  //
  // -----------------------------------------------------------------------------

  /**
   * Perform graph enrichment over the entire graph.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("enrichGraph")
  async enrichGraph(): Promise<any> {
    this._ensureAuthenticated();
    return await this._makeRequest("POST", "enrich_graph");
  }

  // -----------------------------------------------------------------------------
  //
  // Retrieval
  //
  // -----------------------------------------------------------------------------

  /**
   * Conduct a vector and/or KG search.
   * @param query The query to search for.
   * @param vector_search_settings Vector search settings.
   * @param kg_search_settings KG search settings.
   * @returns
   */
  @feature("search")
  async search(
    query: string,
    vector_search_settings?: VectorSearchSettings | Record<string, any>,
    kg_search_settings?: KGSearchSettings | Record<string, any>,
  ): Promise<any> {
    this._ensureAuthenticated();

    const json_data: Record<string, any> = {
      query,
      vector_search_settings,
      kg_search_settings,
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
   * @param kg_search_settings KG search settings.
   * @param rag_generation_config RAG generation configuration.
   * @param task_prompt_override Task prompt override.
   * @param include_title_if_available Include title if available.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("rag")
  async rag(
    query: string,
    vector_search_settings?: VectorSearchSettings | Record<string, any>,
    kg_search_settings?: KGSearchSettings | Record<string, any>,
    rag_generation_config?: GenerationConfig | Record<string, any>,
    task_prompt_override?: string,
    include_title_if_available?: boolean,
  ): Promise<any | AsyncGenerator<string, void, unknown>> {
    this._ensureAuthenticated();

    const json_data: Record<string, any> = {
      query,
      vector_search_settings,
      kg_search_settings,
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
   * @param vector_search_settings Vector search settings.
   * @param kg_search_settings KG search settings.
   * @param rag_generation_config RAG generation configuration.
   * @param task_prompt_override Task prompt override.
   * @param include_title_if_available Include title if available.
   * @returns A promise that resolves to the response from the server.
   */
  @feature("agent")
  async agent(
    messages: Message[],
    vector_search_settings?: VectorSearchSettings | Record<string, any>,
    kg_search_settings?: KGSearchSettings | Record<string, any>,
    rag_generation_config?: GenerationConfig | Record<string, any>,
    task_prompt_override?: string,
    include_title_if_available?: boolean,
  ): Promise<any | AsyncGenerator<string, void, unknown>> {
    this._ensureAuthenticated();

    const json_data: Record<string, any> = {
      messages,
      vector_search_settings,
      kg_search_settings,
      rag_generation_config,
      task_prompt_override,
      include_title_if_available,
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
