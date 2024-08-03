import axios, {
  AxiosInstance,
  Method,
  AxiosResponse,
  AxiosRequestConfig,
} from "axios";
import FormData from "form-data";
import { URLSearchParams } from "url";

let fs: any;
if (typeof window === "undefined") {
  import("fs").then((module) => {
    fs = module;
  });
}

import { feature, initializeTelemetry } from "./feature";
import {
  LoginResponse,
  UserCreate,
  Message,
  RefreshTokenResponse,
  R2RUpdatePromptRequest,
  R2RIngestFilesRequest,
  R2RSearchRequest,
  R2RAgentRequest,
  R2RRAGRequest,
  R2RDeleteRequest,
  R2RAnalyticsRequest,
  R2RUpdateFilesRequest,
  R2RUsersOverviewRequest,
  R2RDocumentsOverviewRequest,
  R2RDocumentChunksRequest,
  R2RLogsRequest,
  R2RPrintRelationshipRequest,
  FilterCriteria,
  AnalysisTypes,
  VectorSearchSettings,
  KGSearchSettings,
  GenerationConfig,
  DEFAULT_GENERATION_CONFIG,
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

  constructor(baseURL: string, prefix: string = "/v1") {
    this.baseUrl = `${baseURL}${prefix}`;
    this.accessToken = null;
    this.refreshToken = null;

    this.axiosInstance = axios.create({
      baseURL: this.baseUrl,
      headers: {
        "Content-Type": "application/json",
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
      ...options,
      responseType: options.responseType || "json",
    };

    config.headers = config.headers || {};

    if (options.data) {
      if (typeof FormData !== "undefined" && options.data instanceof FormData) {
        config.data = options.data;
        delete config.headers["Content-Type"];
      } else if (
        typeof URLSearchParams !== "undefined" &&
        options.data instanceof URLSearchParams
      ) {
        config.data = options.data.toString();
        config.headers["Content-Type"] = "application/x-www-form-urlencoded";
      } else if (typeof options.data === "object") {
        config.data = JSON.stringify(options.data);
        config.headers["Content-Type"] = "application/json";
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

  @feature("register")
  async register(email: string, password: string): Promise<any> {
    const user: UserCreate = { email, password };
    return await this._makeRequest("POST", "register", { data: user });
  }

  @feature("verifyEmail")
  async verifyEmail(verification_code: string): Promise<any> {
    return await this._makeRequest("POST", `verify_email/${verification_code}`);
  }

  @feature("login")
  async login(email: string, password: string): Promise<LoginResponse> {
    let formData;
    if (typeof URLSearchParams !== "undefined") {
      formData = new URLSearchParams();
      formData.append("username", email);
      formData.append("password", password);
    } else {
      formData = `username=${encodeURIComponent(email)}&password=${encodeURIComponent(password)}`;
    }

    const response = await this._makeRequest<LoginResponse>("POST", "login", {
      data: formData,
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

    return response;
  }

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

  private _ensureAuthenticated(): void {
    // if (!this.accessToken) {
    //   throw new Error("Not authenticated. Please login first.");
    // }
  }

  async health(): Promise<any> {
    return await this._makeRequest("GET", "health");
  }

  async serverStats(): Promise<any> {
    this._ensureAuthenticated();
    return await this._makeRequest("GET", "server_stats");
  }

  @feature("updatePrompt")
  async updatePrompt(
    name: string = "default_system",
    template?: string,
    input_types?: Record<string, string>,
  ): Promise<Record<string, any>> {
    this._ensureAuthenticated();

    const request: R2RUpdatePromptRequest = {
      name: name,
    };

    if (template !== undefined) {
      request.template = template;
    }

    if (input_types !== undefined) {
      request.input_types = input_types;
    }

    return await this._makeRequest("POST", "update_prompt", {
      data: request,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  @feature("ingestFiles")
  async ingestFiles(
    files: (string | File | { path: string; name: string })[],
    options: {
      metadatas?: Record<string, any>[];
      document_ids?: string[];
      user_ids?: (string | null)[];
      versions?: string[];
      skip_document_info?: boolean;
    } = {},
  ): Promise<any> {
    this._ensureAuthenticated();

    const formData = new FormData();

    const processPath = async (
      path: string | File | { path: string; name: string },
      index: number,
    ) => {
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
            formData.append(
              "files",
              fs.createReadStream(path),
              path.split("/").pop(),
            );
          }
        } else {
          console.warn(
            "File or folder path provided in browser environment. This is not supported.",
          );
        }
      } else if (path instanceof File) {
        formData.append("files", path);
      } else if ("path" in path) {
        if (typeof window === "undefined") {
          formData.append("files", fs.createReadStream(path.path), path.name);
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

    const request: R2RIngestFilesRequest = {
      metadatas: options.metadatas,
      document_ids: options.document_ids,
      user_ids: options.user_ids,
      versions: options.versions,
      skip_document_info: options.skip_document_info ?? false,
    };

    Object.entries(request).forEach(([key, value]) => {
      if (value !== undefined) {
        formData.append(key, JSON.stringify(value));
      }
    });

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

  @feature("updateFiles")
  async updateFiles(
    files: (File | { path: string; name: string })[],
    options: {
      document_ids: string[];
      metadatas?: Record<string, any>[];
    },
  ): Promise<any> {
    this._ensureAuthenticated();

    const formData = new FormData();

    if (files.length !== options.document_ids.length) {
      throw new Error("Each file must have a corresponding document ID.");
    }

    files.forEach((file, index) => {
      if ("path" in file) {
        if (typeof window === "undefined") {
          formData.append(`files`, fs.createReadStream(file.path), file.name);
        } else {
          console.warn(
            "File path provided in browser environment. This is not supported.",
          );
        }
      } else {
        formData.append(`files`, file);
      }
    });

    const request: R2RUpdateFilesRequest = {
      metadatas: options.metadatas,
      document_ids: options.document_ids,
    };

    Object.entries(request).forEach(([key, value]) => {
      if (value !== undefined) {
        formData.append(key, JSON.stringify(value));
      }
    });

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

  @feature("search")
  async search(
    query: string,
    use_vector_search?: boolean,
    search_filters?: Record<string, any>,
    search_limit?: number,
    do_hybrid_search?: boolean,
    use_kg_search?: boolean,
    kg_agent_generation_config?: GenerationConfig,
  ): Promise<any> {
    this._ensureAuthenticated();

    const vector_search_settings: VectorSearchSettings = {
      use_vector_search: use_vector_search || true,
      search_filters: search_filters || {},
      search_limit: search_limit || 10,
      do_hybrid_search: do_hybrid_search || false,
    };

    const kg_search_settings: KGSearchSettings = {
      use_kg_search: use_kg_search !== undefined ? use_kg_search : false,
      agent_generation_config: kg_agent_generation_config
        ? { ...DEFAULT_GENERATION_CONFIG, ...kg_agent_generation_config }
        : undefined,
    };

    const request: R2RSearchRequest = {
      query,
      vector_search_settings,
      kg_search_settings,
    };

    return await this._makeRequest("POST", "search", { data: request });
  }

  @feature("rag")
  async rag(params: {
    query: string;
    use_vector_search?: boolean;
    search_filters?: Record<string, any>;
    search_limit?: number;
    do_hybrid_search?: boolean;
    use_kg_search?: boolean;
    kg_generation_config?: Record<string, any>;
    rag_generation_config?: Record<string, any>;
  }): Promise<any> {
    this._ensureAuthenticated();

    const {
      query,
      use_vector_search = true,
      search_filters = {},
      search_limit = 10,
      do_hybrid_search = false,
      use_kg_search = false,
      kg_generation_config = {},
      rag_generation_config = {},
    } = params;

    const vector_search_settings: Record<string, any> = {
      use_vector_search,
      search_filters,
      search_limit,
      do_hybrid_search,
    };

    const kg_search_settings: Record<string, any> = {
      use_kg_search,
      agent_generation_config: {
        ...DEFAULT_GENERATION_CONFIG,
        ...kg_generation_config,
      },
    };

    const request: R2RRAGRequest = {
      query,
      vector_search_settings,
      kg_search_settings,
      rag_generation_config: {
        ...DEFAULT_GENERATION_CONFIG,
        ...rag_generation_config,
      },
    };

    if (rag_generation_config && rag_generation_config.stream) {
      return this.streamRag(request);
    } else {
      return await this._makeRequest("POST", "rag", { data: request });
    }
  }

  @feature("streamingRag")
  private async streamRag(
    request: R2RRAGRequest,
  ): Promise<ReadableStream<Uint8Array>> {
    this._ensureAuthenticated();

    return this._makeRequest<ReadableStream<Uint8Array>>("POST", "rag", {
      data: request,
      headers: {
        "Content-Type": "application/json",
      },
      responseType: "stream",
    });
  }

  @feature("delete")
  async delete(keys: string[], values: any[]): Promise<any> {
    this._ensureAuthenticated();

    const request: R2RDeleteRequest = {
      keys,
      values,
    };

    return this._makeRequest("DELETE", "delete", {
      data: request,
      headers: { "Content-Type": "application/json" },
    });
  }

  @feature("logs")
  async logs(
    log_type_filter?: string,
    max_runs_requested: number = 100,
  ): Promise<any> {
    this._ensureAuthenticated();

    const request: R2RLogsRequest = {
      log_type_filter: log_type_filter || null,
      max_runs_requested: max_runs_requested,
    };

    return this._makeRequest("POST", "logs", {
      data: request,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  @feature("appSettings")
  async appSettings(): Promise<any> {
    this._ensureAuthenticated();

    return this._makeRequest("GET", "app_settings");
  }

  @feature("analytics")
  async analytics(
    filter_criteria: FilterCriteria,
    analysis_types: AnalysisTypes,
  ): Promise<any> {
    this._ensureAuthenticated();

    const request: R2RAnalyticsRequest = {
      filter_criteria,
      analysis_types,
    };

    return this._makeRequest("POST", "analytics", {
      data: request,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  @feature("usersOverview")
  async usersOverview(user_ids?: string[]): Promise<any> {
    this._ensureAuthenticated();

    const request: R2RUsersOverviewRequest = {
      user_ids: user_ids || [],
    };

    return this._makeRequest("POST", "users_overview", {
      data: request,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  @feature("documentsOverview")
  async documentsOverview(
    document_ids?: string[],
    user_ids?: string[],
  ): Promise<any> {
    this._ensureAuthenticated();

    const request: R2RDocumentsOverviewRequest = {
      document_ids: document_ids || [],
      user_ids: user_ids || [],
    };

    return this._makeRequest("POST", "documents_overview", {
      data: request,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  @feature("documentChunks")
  async documentChunks(document_id: string): Promise<any> {
    this._ensureAuthenticated();

    const request: R2RDocumentChunksRequest = {
      document_id,
    };

    return this._makeRequest("POST", "document_chunks", {
      data: request,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  @feature("inspectKnowledgeGraph")
  async inspectKnowledgeGraph(limit: number = 100): Promise<any> {
    this._ensureAuthenticated();

    const request: R2RPrintRelationshipRequest = {
      limit,
    };

    return this._makeRequest("POST", "inspect_knowledge_graph", {
      data: request,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

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

  @feature("requestPasswordReset")
  async requestPasswordReset(email: string): Promise<any> {
    return this._makeRequest("POST", "request_password_reset", {
      data: { email },
    });
  }

  @feature("confirmPasswordReset")
  async confirmPasswordReset(
    resetToken: string,
    newPassword: string,
  ): Promise<any> {
    return this._makeRequest("POST", `reset_password/${resetToken}`, {
      data: { new_password: newPassword },
    });
  }

  @feature("logout")
  async logout(): Promise<any> {
    this._ensureAuthenticated();

    const response = await this._makeRequest("POST", "logout");
    this.accessToken = null;
    this.refreshToken = null;
    return response;
  }

  @feature("deleteUser")
  async deleteUser(password: string): Promise<any> {
    this._ensureAuthenticated();
    const response = await this._makeRequest("DELETE", "user", {
      data: { password },
    });
    this.accessToken = null;
    this.refreshToken = null;
    return response;
  }

  @feature("agent")
  async agent(params: {
    messages: Message[];
    use_vector_search?: boolean;
    search_filters?: Record<string, any>;
    search_limit?: number;
    do_hybrid_search?: boolean;
    use_kg_search?: boolean;
    kg_search_generation_config?: Record<string, any>;
    rag_generation_config?: GenerationConfig;
    task_prompt_override?: string;
    include_title_if_available?: boolean;
  }): Promise<any> {
    this._ensureAuthenticated();

    const {
      messages,
      use_vector_search = true,
      search_filters = {},
      search_limit = 10,
      do_hybrid_search = false,
      use_kg_search = false,
      kg_search_generation_config,
      rag_generation_config,
      task_prompt_override,
      include_title_if_available = true,
    } = params;

    const request: R2RAgentRequest = {
      messages,
      vector_search_settings: {
        use_vector_search,
        search_filters,
        search_limit,
        do_hybrid_search,
      },
      kg_search_settings: {
        use_kg_search,
        kg_search_generation_config,
      },
      rag_generation_config,
      task_prompt_override,
      include_title_if_available,
    };

    if (rag_generation_config && rag_generation_config.stream) {
      return this.streamAgent(request);
    } else {
      return await this._makeRequest("POST", "agent", { data: request });
    }
  }

  private async streamAgent(
    request: R2RAgentRequest,
  ): Promise<ReadableStream<Uint8Array>> {
    this._ensureAuthenticated();

    return this._makeRequest<ReadableStream<Uint8Array>>("POST", "agent", {
      data: request,
      headers: {
        "Content-Type": "application/json",
      },
      responseType: "stream",
    });
  }
}

export default r2rClient;
