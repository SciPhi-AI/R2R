import { r2rClient } from "../../r2rClient";
import {
  WrappedGenericMessageResponse,
  WrappedLogsResponse,
  WrappedServerStatsResponse,
  WrappedSettingsResponse,
} from "../../types";

export class SystemClient {
  constructor(private client: r2rClient) {}

  /**
   * Check the health of the R2R server.
   */
  async health(): Promise<WrappedGenericMessageResponse> {
    return await this.client.makeRequest("GET", "health");
  }

  /**
   * Get logs from the server.
   * @param options
   * @returns
   */
  async logs(options: {
    runTypeFilter?: string;
    offset?: number;
    limit?: number;
  }): Promise<WrappedLogsResponse> {
    const params: Record<string, any> = {
      offset: options.offset ?? 0,
      limit: options.limit ?? 100,
    };

    if (options.runTypeFilter) {
      params.runTypeFilter = options.runTypeFilter;
    }

    return this.client.makeRequest("GET", "system/logs", { params });
  }

  /**
   * Get the configuration settings for the R2R server.
   * @returns
   */
  async settings(): Promise<WrappedSettingsResponse> {
    return await this.client.makeRequest("GET", "system/settings");
  }

  /**
   * Get statistics about the server, including the start time, uptime, CPU usage, and memory usage.
   * @returns
   */
  async status(): Promise<WrappedServerStatsResponse> {
    return await this.client.makeRequest("GET", "system/status");
  }
}
