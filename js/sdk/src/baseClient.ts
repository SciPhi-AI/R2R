import axios, {
  AxiosInstance,
  Method,
  AxiosResponse,
  AxiosRequestConfig,
} from "axios";
import FormData from "form-data";
import { ensureCamelCase } from "./utils";

let fs: any;
if (typeof window === "undefined") {
  import("fs").then((module) => {
    fs = module;
  });
}

function handleRequestError(response: AxiosResponse): void {
  if (response.status < 400) {
    return;
  }

  let message: string;
  const errorContent = ensureCamelCase(response.data);

  if (typeof errorContent === "object" && errorContent !== null) {
    message =
      errorContent.message ||
      (errorContent.detail && errorContent.detail.message) ||
      (typeof errorContent.detail === "string" && errorContent.detail) ||
      JSON.stringify(errorContent);
  } else {
    message = String(errorContent);
  }

  throw new Error(`Status ${response.status}: ${message}`);
}

export abstract class BaseClient {
  protected axiosInstance: AxiosInstance;
  protected baseUrl: string;
  protected accessToken: string | null;
  protected refreshToken: string | null;
  protected anonymousTelemetry: boolean;

  // NEW: declare enableAutoRefresh
  protected enableAutoRefresh: boolean;

  constructor(
    baseURL: string,
    prefix: string = "",
    anonymousTelemetry = true,
    enableAutoRefresh = false,
  ) {
    this.baseUrl = `${baseURL}${prefix}`;
    this.accessToken = null;
    this.refreshToken = null;
    this.anonymousTelemetry = anonymousTelemetry;

    // Add this assignment
    this.enableAutoRefresh = enableAutoRefresh;

    this.axiosInstance = axios.create({
      baseURL: this.baseUrl,
      headers: {
        "Content-Type": "application/json",
      },
    });
  }

  protected async _makeRequest<T = any>(
    method: Method,
    endpoint: string,
    options: any = {},
    version: "v3" = "v3",
  ): Promise<T> {
    const url = `/${version}/${endpoint}`;
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
            return `${encodeURIComponent(key)}=${encodeURIComponent(
              String(value),
            )}`;
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
                `${encodeURIComponent(key)}=${encodeURIComponent(
                  options.data[key],
                )}`,
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
      const response = await fetch(`${this.baseUrl}/${version}/${endpoint}`, {
        method,
        headers: fetchHeaders,
        body: config.data,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(
          `HTTP error! status: ${response.status}: ${
            ensureCamelCase(errorData).message || "Unknown error"
          }`,
        );
      }

      return response.body as unknown as T;
    }

    try {
      const response = await this.axiosInstance.request(config);

      if (options.responseType === "blob") {
        return response.data as T;
      } else if (options.responseType === "arraybuffer") {
        if (options.returnFullResponse) {
          return response as unknown as T;
        }
        return response.data as T;
      }

      const responseData = options.returnFullResponse
        ? { ...response, data: ensureCamelCase(response.data) }
        : ensureCamelCase(response.data);

      return responseData as T;
    } catch (error) {
      if (axios.isAxiosError(error) && error.response) {
        handleRequestError(error.response);
      }
      throw error;
    }
  }

  protected _ensureAuthenticated(): void {
    if (!this.accessToken) {
      throw new Error("Not authenticated. Please login first.");
    }
  }

  setTokens(accessToken: string, refreshToken: string): void {
    this.accessToken = accessToken;
    this.refreshToken = refreshToken;
  }
}
