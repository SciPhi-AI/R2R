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

import { initializeTelemetry } from "./feature";

type RefreshTokenResponse = {
  results: {
    accessToken: string;
    refreshToken: string;
  };
};

interface R2RClientOptions {
  enableAutoRefresh?: boolean;
  getTokensCallback?: () => {
    accessToken: string | null;
    refreshToken: string | null;
  };
  setTokensCallback?: (accessToken: string | null, refreshToken: string | null) => void;
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
    options: R2RClientOptions = {}
  ) {
    super(baseURL, "", anonymousTelemetry, options.enableAutoRefresh);

    console.log("[r2rClient] Creating new client with baseURL =", baseURL);

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
          console.log(`[r2rClient] Attaching access token to request: ${accessToken.slice(0, 15)}...`);
          config.headers["Authorization"] = `Bearer ${accessToken}`;
        } else {
          console.log("[r2rClient] No access token found, sending request without Authorization header");
        }
        return config;
      },
      (error) => {
        console.error("[r2rClient] Request interceptor error:", error);
        return Promise.reject(error);
      }
    );

    // 2) Response interceptor: see if we got 401/403 => attempt to refresh
    this.setupResponseInterceptor();
  }

  private setupResponseInterceptor() {
    this.axiosInstance.interceptors.response.use(
      (response) => response,
      async (error: AxiosError) => {
        // Some logs to see what's going on
        console.warn("[r2rClient] Response interceptor caught an error:", error);
        const status = error.response?.status;
        const failingUrl = error.config?.url;
        console.warn("[r2rClient] Failing request URL:", failingUrl, "status =", status);
        console.warn("failingUrl?.includes('/v3/users/refresh-token') = ", failingUrl?.includes("/v3/users/refresh-token"))

        // 1) If the refresh endpoint itself fails => don't try again
        if (failingUrl?.includes("/v3/users/refresh-token")) {
          console.error("[r2rClient] Refresh call itself returned 401/403 => logging out");
          this.onRefreshFailedCallback?.();
          return Promise.reject(error);
        }

        // 2) If normal request => attempt refresh if 401/403
        if ((status === 401 || status === 403) && this.getTokensCallback) {
          const { refreshToken } = this.getTokensCallback();
          if (!refreshToken) {
            console.error("[r2rClient] No refresh token found => logout");
            this.onRefreshFailedCallback?.();
            return Promise.reject(error);
          }

          // Attempt refresh
          try {
            console.log("[r2rClient] Attempting token refresh...");
            const refreshResponse = (await this.users.refreshAccessToken()) as RefreshTokenResponse;
            const newAccessToken = refreshResponse.results.accessToken;
            const newRefreshToken = refreshResponse.results.refreshToken;
            console.log("[r2rClient] Refresh call succeeded; new access token:", newAccessToken.slice(0, 15), "...");

            // set new tokens
            this.setTokens(newAccessToken, newRefreshToken);

            // Re-try the original request
            if (error.config) {
              error.config.headers["Authorization"] = `Bearer ${newAccessToken}`;
              console.log("[r2rClient] Retrying original request with new access token...");
              return this.axiosInstance.request(error.config);
            } else {
              console.warn("[r2rClient] No request config found to retry. Possibly manual re-fetch needed");
            }
          } catch (refreshError) {
            console.error("[r2rClient] Refresh attempt failed => logging out. Error was:", refreshError);
            this.onRefreshFailedCallback?.();
            return Promise.reject(refreshError);
          }
        }

        // 3) If not a 401/403, or no refresh logic => just reject
        console.log("[r2rClient] Non-401/403 error => rejecting request");
        return Promise.reject(error);
      }
    );
  }

  public makeRequest<T = any>(
    method: Method,
    endpoint: string,
    options: any = {}
  ): Promise<T> {
    console.log(`[r2rClient] makeRequest: ${method.toUpperCase()} ${endpoint}`);
    return this._makeRequest(method, endpoint, options, "v3");
  }

  public getRefreshToken(): string | null {
    return this.refreshToken;
  }

  public setTokens(accessToken: string | null, refreshToken: string | null): void {
    // Optional: log the changes, but be careful not to log full tokens in prod
    console.log("[r2rClient] Setting tokens. Access token:", accessToken?.slice(0, 15), "... refresh token:", refreshToken?.slice(0, 15), "...");
    super.setTokens(accessToken || "", refreshToken || "");
    this.setTokensCallback?.(accessToken, refreshToken);
  }
}

export default r2rClient;


// import axios, { Method, AxiosError } from "axios";
// import { BaseClient } from "./baseClient";

// import { ChunksClient } from "./v3/clients/chunks";
// import { CollectionsClient } from "./v3/clients/collections";
// import { ConversationsClient } from "./v3/clients/conversations";
// import { DocumentsClient } from "./v3/clients/documents";
// import { GraphsClient } from "./v3/clients/graphs";
// import { IndiciesClient } from "./v3/clients/indices";
// import { PromptsClient } from "./v3/clients/prompts";
// import { RetrievalClient } from "./v3/clients/retrieval";
// import { SystemClient } from "./v3/clients/system";
// import { UsersClient } from "./v3/clients/users";

// import { initializeTelemetry } from "./feature";

// type RefreshTokenResponse = {
//   results: {
//     accessToken: string;
//     refreshToken: string;
//   };
// };

// interface R2RClientOptions {
//   enableAutoRefresh?: boolean;
//   getTokensCallback?: () => {
//     accessToken: string | null;
//     refreshToken: string | null;
//   };
//   setTokensCallback?: (accessToken: string | null, refreshToken: string | null) => void;
//   onRefreshFailedCallback?: () => void;
// }

// export class r2rClient extends BaseClient {
//   public readonly chunks: ChunksClient;
//   public readonly collections: CollectionsClient;
//   public readonly conversations: ConversationsClient;
//   public readonly documents: DocumentsClient;
//   public readonly graphs: GraphsClient;
//   public readonly indices: IndiciesClient;
//   public readonly prompts: PromptsClient;
//   public readonly retrieval: RetrievalClient;
//   public readonly system: SystemClient;
//   public readonly users: UsersClient;

//   private getTokensCallback?: R2RClientOptions["getTokensCallback"];
//   private setTokensCallback?: R2RClientOptions["setTokensCallback"];
//   private onRefreshFailedCallback?: R2RClientOptions["onRefreshFailedCallback"];

//   constructor(
//     baseURL: string,
//     anonymousTelemetry = true,
//     options: R2RClientOptions = {}
//   ) {
//     // We'll still pass enableAutoRefresh to the base client
//     // in case you want the base class to know about it.
//     super(baseURL, "", anonymousTelemetry, options.enableAutoRefresh);

//     // instantiate v3 sub-clients
//     this.chunks = new ChunksClient(this);
//     this.collections = new CollectionsClient(this);
//     this.conversations = new ConversationsClient(this);
//     this.documents = new DocumentsClient(this);
//     this.graphs = new GraphsClient(this);
//     this.indices = new IndiciesClient(this);
//     this.prompts = new PromptsClient(this);
//     this.retrieval = new RetrievalClient(this);
//     this.system = new SystemClient(this);
//     this.users = new UsersClient(this);

//     // optional telemetry init
//     initializeTelemetry(this.anonymousTelemetry);

//     // Create our axios instance
//     this.axiosInstance = axios.create({
//       baseURL: this.baseUrl,
//       headers: {
//         "Content-Type": "application/json",
//       },
//       paramsSerializer: (params) => {
//         const parts: string[] = [];
//         Object.entries(params).forEach(([key, value]) => {
//           if (Array.isArray(value)) {
//             value.forEach((v) =>
//               parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(v)}`)
//             );
//           } else {
//             parts.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
//           }
//         });
//         return parts.join("&");
//       },
//       transformRequest: [
//         (data) => {
//           if (typeof data === "string") {
//             return data;
//           }
//           return JSON.stringify(data);
//         },
//       ],
//     });

//     // store callbacks
//     this.getTokensCallback = options.getTokensCallback;
//     this.setTokensCallback = options.setTokensCallback;
//     this.onRefreshFailedCallback = options.onRefreshFailedCallback;

//     // If you still want to attach the token on each request,
//     // we can keep a REQUEST interceptor just for that part:
//     this.axiosInstance.interceptors.request.use(
//       (config) => {
//         if (this.getTokensCallback) {
//           const { accessToken } = this.getTokensCallback();
//           if (accessToken) {
//             config.headers["Authorization"] = `Bearer ${accessToken}`;
//           }
//         }
//         return config;
//       },
//       (error) => Promise.reject(error)
//     );

//     // Now set up our RESPONSE interceptor that tries to refresh
//     // only after we get 401/403 from a normal request.
//     this.setupResponseInterceptor();
//   }

//   private setupResponseInterceptor() {
//     this.axiosInstance.interceptors.response.use(
//       (response) => response,
//       async (error: AxiosError) => {
//         const status = error.response?.status;

//         // 1) If we got a 401/403 *while calling the refresh endpoint itself*,
//         //    DO NOT attempt to refresh again. Just fail out (and likely logout).
//         if (error.config?.url?.includes("/users/refreshAccessToken")) {
//           console.error("Refresh call itself failed. Logging out...");
//           if (this.onRefreshFailedCallback) {
//             this.onRefreshFailedCallback();
//           }
//           return Promise.reject(error);
//         }

//         // 2) If we got a 401 or 403 on a *normal* request, let's attempt to refresh:
//         if ((status === 401 || status === 403) && this.getTokensCallback) {
//           const { refreshToken } = this.getTokensCallback();
//           if (!refreshToken) {
//             // we have no refresh token => can't do anything but fail
//             console.error("No refresh token available, logging out...");
//             if (this.onRefreshFailedCallback) {
//               this.onRefreshFailedCallback();
//             }
//             return Promise.reject(error);
//           }

//           try {
//             // Attempt a refresh call
//             console.log("Attempting to refresh tokens...");

//             // Use our built-in user client method:
//             const refreshResponse = (await this.users.refreshAccessToken()) as RefreshTokenResponse;

//             // If it works, we set new tokens and re-try the original request.
//             const newAccessToken = refreshResponse.results.accessToken;
//             const newRefreshToken = refreshResponse.results.refreshToken;

//             if (this.setTokensCallback) {
//               this.setTokensCallback(newAccessToken, newRefreshToken);
//             }
//             // also update the baseClient
//             this.accessToken = newAccessToken;
//             this.refreshToken = newRefreshToken;

//             // Re-try the original request with updated tokens
//             if (error.config) {
//               // attach the new token
//               error.config.headers["Authorization"] = `Bearer ${newAccessToken}`;
//               // now re-do the original request
//               return this.axiosInstance.request(error.config);
//             }
//           } catch (refreshError) {
//             console.error("Failed to refresh token:", refreshError);
//             // On refresh failure => logout
//             if (this.onRefreshFailedCallback) {
//               this.onRefreshFailedCallback();
//             }
//           }
//         }

//         // If none of the above conditions apply, just reject as normal
//         return Promise.reject(error);
//       }
//     );
//   }

//   // Optionally, if you *don’t* want to rely on interceptors, you could implement
//   // this logic inline in makeRequest. But usually the interceptor approach is easier.
//   public makeRequest<T = any>(
//     method: Method,
//     endpoint: string,
//     options: any = {}
//   ): Promise<T> {
//     return this._makeRequest(method, endpoint, options, "v3");
//   }

//   public getRefreshToken(): string | null {
//     return this.refreshToken;
//   }

//   // override setTokens if you want to also call setTokensCallback
//   public setTokens(accessToken: string | null, refreshToken: string | null): void {
//     super.setTokens(accessToken || "", refreshToken || "");
//     if (this.setTokensCallback) {
//       this.setTokensCallback(accessToken, refreshToken);
//     }
//   }
// }

// export default r2rClient;
