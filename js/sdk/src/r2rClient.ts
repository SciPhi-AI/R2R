import axios, { Method } from "axios";

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

import { initializeTelemetry } from "./feature";

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
}

export default r2rClient;
