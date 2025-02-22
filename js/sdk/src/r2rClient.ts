import axios, { Method, AxiosError } from "axios";
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
  fs = require("fs");
}

type RefreshTokenResponse = {
  results: {
    accessToken: { token: string };
    refreshToken: { token: string };
  };
};

interface R2RClientOptions {
  enableAutoRefresh?: boolean;
  getTokensCallback?: () => {
    accessToken: string | null;
    refreshToken: string | null;
  };
  setTokensCallback?: (
    accessToken: string | null,
    refreshToken: string | null,
  ) => void;
  onRefreshFailedCallback?: () => void;
}

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

  private getTokensCallback?: R2RClientOptions["getTokensCallback"];
  private setTokensCallback?: R2RClientOptions["setTokensCallback"];
  private onRefreshFailedCallback?: R2RClientOptions["onRefreshFailedCallback"];

  constructor(
    baseURL: string,
    anonymousTelemetry = true,
    options: R2RClientOptions = {},
  ) {
    super(baseURL, "", anonymousTelemetry, options.enableAutoRefresh);

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

    this.axiosInstance = axios.create({
      baseURL: this.baseUrl,
      headers: {
        "Content-Type": "application/json",
      },
    });

    this.getTokensCallback = options.getTokensCallback;
    this.setTokensCallback = options.setTokensCallback;
    this.onRefreshFailedCallback = options.onRefreshFailedCallback;

    // 1) Request interceptor: attach current access token (if any)
    this.axiosInstance.interceptors.request.use(
      (config) => {
        const tokenData = this.getTokensCallback?.();
        const accessToken = tokenData?.accessToken || null;
        if (accessToken) {
          config.headers["Authorization"] = `Bearer ${accessToken}`;
        }
        return config;
      },
      (error) => {
        console.error("[r2rClient] Request interceptor error:", error);
        return Promise.reject(error);
      },
    );

    // 2) Response interceptor: see if we got 401/403 => attempt to refresh
    this.setupResponseInterceptor();
  }

  private setupResponseInterceptor() {
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        const status = error.response?.status;
        const failingUrl = error.config?.url;
        const errorData = error.response?.data as {
          message?: string;
          error_code?: string;
        };

        // 1) If the refresh endpoint itself fails => don't try again
        if (failingUrl?.includes("/v3/users/refresh-token")) {
          console.error(
            "[r2rClient] Refresh call itself returned 401/403 => logging out",
          );
          this.onRefreshFailedCallback?.();
          return Promise.reject(error);
        }

        // 2) If normal request => attempt refresh IF it's really an invalid/expired token
        // We'll check either an explicit "error_code" or text in "message"
        // Adjust to match your server's structure!
        const isTokenError =
          !!errorData?.error_code &&
          errorData.error_code.toUpperCase() === "TOKEN_EXPIRED";

        // Or fallback to matching common phrases if no error_code is set:
        const msg = (errorData?.message || "").toLowerCase();
        const looksLikeTokenIssue =
          msg.includes("invalid token") ||
          msg.includes("token expired") ||
          msg.includes("credentials");

        // If either of those checks is true, we consider it an auth token error:
        const isAuthError = isTokenError || looksLikeTokenIssue;

        if (
          (status === 401 || status === 403) &&
          this.getTokensCallback &&
          isAuthError
        ) {
          // Check if we have a refresh token
          const { refreshToken } = this.getTokensCallback();
          if (!refreshToken) {
            console.error("[r2rClient] No refresh token found => logout");
            this.onRefreshFailedCallback?.();
            return Promise.reject(error);
          }

          // Attempt refresh
          try {
            const refreshResponse = await this.users.refreshAccessToken();
            const newAccessToken = refreshResponse.results.accessToken.token;
            const newRefreshToken = refreshResponse.results.refreshToken.token;

            // set new tokens
            this.setTokens(newAccessToken, newRefreshToken);

            // Re-try the original request
            if (error.config) {
              error.config.headers["Authorization"] =
                `Bearer ${newAccessToken}`;
              return this.axiosInstance.request(error.config);
            } else {
              console.warn(
                "[r2rClient] No request config found to retry. Possibly manual re-fetch needed",
              );
            }
          } catch (refreshError) {
            console.error(
              "[r2rClient] Refresh attempt failed => logging out. Error was:",
              refreshError,
            );
            this.onRefreshFailedCallback?.();
            return Promise.reject(refreshError);
          }
        }

        // 3) If not a 401/403 or it's a 401/403 that isn't token-related => just reject
        return Promise.reject(error);
      },
    );
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

  public setTokens(
    accessToken: string | null,
    refreshToken: string | null,
  ): void {
    super.setTokens(accessToken || "", refreshToken || "");
    this.setTokensCallback?.(accessToken, refreshToken);
  }
}

export default r2rClient;
