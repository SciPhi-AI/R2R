import { r2rClient } from "../../r2rClient";

export class SystemClient {
  constructor(private client: r2rClient) {}

  /**
   * Check the health of the R2R server.
   */
  async health(): Promise<any> {
    return await this.client.makeRequest("GET", "health");
  }

  /**
   * Get logs from the server.
   * @param options
   * @returns
   */
  async logs(options: {
    run_type_filter?: string;
    offset?: number;
    limit?: number;
  }): Promise<any> {
    const params: Record<string, any> = {
      offset: options.offset ?? 0,
      limit: options.limit ?? 100,
    };

    if (options.run_type_filter) {
      params.run_type_filter = options.run_type_filter;
    }

    return this.client.makeRequest("GET", "system/logs", { params });
  }

  /**
   * Get the configuration settings for the R2R server.
   * @returns
   */
  async settings(): Promise<any> {
    return await this.client.makeRequest("GET", "system/settings");
  }

  /**
   * Get statistics about the server, including the start time, uptime, CPU usage, and memory usage.
   * @returns
   */
  async status(): Promise<any> {
    return await this.client.makeRequest("GET", "system/status");
  }
}
