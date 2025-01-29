import { r2rClient } from "../../r2rClient";
import {
  WrappedGenericMessageResponse,
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
   * Get the configuration settings for the R2R server.
   * @returns
   */
  async settings(): Promise<WrappedSettingsResponse> {
    return await this.client.makeRequest("GET", "system/settings");
  }

  /**
   * Get statistics about the server, including the start time, uptime,
   * CPU usage, and memory usage.
   * @returns
   */
  async status(): Promise<WrappedServerStatsResponse> {
    return await this.client.makeRequest("GET", "system/status");
  }
}
