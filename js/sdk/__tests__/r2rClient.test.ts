import { r2rClient } from "../src/r2rClient";
import axios from "axios";
import { describe, test, beforeEach, expect, jest } from "@jest/globals";

jest.mock("axios");

describe("R2RClient", () => {
  let client: r2rClient;
  let mockAxiosInstance: any;

  beforeEach(() => {
    mockAxiosInstance = {
      post: jest.fn(),
      request: jest.fn(),
      defaults: { baseURL: "http://0.0.0.0:7272/v2" },
    };

    (axios.create as jest.Mock).mockReturnValue(mockAxiosInstance);

    client = new r2rClient("http://0.0.0.0:7272");
  });

  describe("Mocked Tests", () => {
    test("should correctly set the baseURL with prefix", () => {
      expect((client as any).axiosInstance.defaults.baseURL).toBe(
        "http://0.0.0.0:7272/v2",
      );
    });

    test("health should return data from the /health endpoint", async () => {
      const mockResponse = { response: "ok" };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      const result = await client.health();
      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "GET",
        url: "health",
        headers: {},
        responseType: "json",
      });
    });
  });
});
