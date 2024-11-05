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

  describe("Authentication Methods", () => {
    test("register should send POST request to /register with correct data", async () => {
      const mockResponse = { success: true };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      const email = "test@example.com";
      const password = "password123";
      const result = await client.register(email, password);

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: "register",
        data: JSON.stringify({ email, password }),
        headers: {
          "Content-Type": "application/json",
        },
        responseType: "json",
      });
    });

    test("login should send POST request to /login with correct data and set tokens", async () => {
      const mockResponse = {
        results: {
          access_token: { token: "access-token", token_type: "access_token" },
          refresh_token: {
            token: "refresh-token",
            token_type: "refresh_token",
          },
        },
      };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      const email = "test@example.com";
      const password = "password123";
      const result = await client.login(email, password);

      expect(result).toEqual(mockResponse.results);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: "login",
        data: "username=test%40example.com&password=password123",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        responseType: "json",
      });
      // Check that tokens are set
      expect((client as any).accessToken).toBe("access-token");
      expect((client as any).refreshToken).toBe("refresh-token");
    });

    test("verifyEmail should send POST request to /verify_email with correct data", async () => {
      const mockResponse = { success: true };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      const email = "test@example.com";
      const verification_code = "123456";
      const result = await client.verifyEmail(email, verification_code);

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: "verify_email",
        data: JSON.stringify({ email, verification_code }),
        headers: {
          "Content-Type": "application/json",
        },
        responseType: "json",
      });
    });

    test("requestPasswordReset should send POST request to /request_password_reset with correct data", async () => {
      const mockResponse = { success: true };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      const email = "test@example.com";
      const result = await client.requestPasswordReset(email);

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: "request_password_reset",
        data: '"test@example.com"',
        headers: {
          "Content-Type": "application/json",
        },
        responseType: "json",
        params: undefined,
      });
    });

    test("logout should send POST request to /logout and clear tokens", async () => {
      mockAxiosInstance.request.mockResolvedValue({ data: {} });

      // Set tokens first
      (client as any).accessToken = "access-token";
      (client as any).refreshToken = "refresh-token";

      const result = await client.logout();

      expect(result).toEqual({});
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: "logout",
        headers: {
          Authorization: "Bearer access-token",
        },
        responseType: "json",
      });
      expect((client as any).accessToken).toBeNull();
      expect((client as any).refreshToken).toBeNull();
    });

    test("user should send GET request to /user and return data", async () => {
      const mockResponse = { id: "user-id", email: "test@example.com" };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set accessToken
      (client as any).accessToken = "access-token";

      const result = await client.user();

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "GET",
        url: "user",
        headers: {
          Authorization: "Bearer access-token",
        },
        responseType: "json",
      });
    });

    test("updateUser should send PUT request to /user with correct data", async () => {
      const mockResponse = { success: true };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set accessToken
      (client as any).accessToken = "access-token";

      const userId = "user-id";
      const email = "new@example.com";
      const name = "New Name";
      const bio = "New Bio";
      const profilePicture = "http://example.com/pic.jpg";
      const isSuperuser = true;

      const result = await client.updateUser(
        userId,
        email,
        isSuperuser,
        name,
        bio,
        profilePicture,
      );

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "PUT",
        url: "user",
        data: JSON.stringify({
          user_id: userId,
          email,
          is_superuser: isSuperuser,
          name,
          bio,
          profile_picture: profilePicture,
        }),
        headers: {
          Authorization: "Bearer access-token",
          "Content-Type": "application/json",
        },
        responseType: "json",
      });
    });

    test("refreshAccessToken should send POST request to /refresh_access_token and update tokens", async () => {
      const mockResponse = {
        results: {
          access_token: {
            token: "new-access-token",
            token_type: "access_token",
          },
          refresh_token: {
            token: "new-refresh-token",
            token_type: "refresh_token",
          },
        },
      };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set refreshToken
      (client as any).refreshToken = "old-refresh-token";

      const result = await client.refreshAccessToken();

      expect(result).toEqual(mockResponse);
      expect((client as any).accessToken).toBe("new-access-token");
      expect((client as any).refreshToken).toBe("new-refresh-token");

      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: "refresh_access_token",
        data: "old-refresh-token",
        headers: {
          "Content-Type": "application/x-www-form-urlencoded",
        },
        responseType: "json",
      });
    });

    test("changePassword should send POST request to /change_password with correct data", async () => {
      const mockResponse = { success: true };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set accessToken
      (client as any).accessToken = "access-token";

      const current_password = "old-password";
      const new_password = "new-password";

      const result = await client.changePassword(
        current_password,
        new_password,
      );

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: "change_password",
        data: JSON.stringify({
          current_password,
          new_password,
        }),
        headers: {
          Authorization: "Bearer access-token",
          "Content-Type": "application/json",
        },
        responseType: "json",
      });
    });

    test("confirmPasswordReset should send POST request to /reset_password/{resetToken} with correct data", async () => {
      const mockResponse = { success: true };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      const resetToken = "reset-token";
      const newPassword = "new-password";

      const result = await client.confirmPasswordReset(resetToken, newPassword);

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: `reset_password/${resetToken}`,
        data: JSON.stringify({ new_password: newPassword }),
        headers: {
          "Content-Type": "application/json",
        },
        responseType: "json",
      });
    });

    test("deleteUser should send DELETE request to /user/{userId} with correct data", async () => {
      const mockResponse = { success: true };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set accessToken
      (client as any).accessToken = "access-token";

      const userId = "user-id";
      const password = "password123";

      const result = await client.deleteUser(userId, password);

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "DELETE",
        url: `user/${userId}`,
        data: JSON.stringify({ password }),
        headers: {
          Authorization: "Bearer access-token",
          "Content-Type": "application/json",
        },
        responseType: "json",
      });
    });
  });

  describe("Ingestion Methods", () => {
    test("ingestChunks should send POST request to /ingest_chunks with correct data", async () => {
      const mockResponse = { success: true };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set accessToken
      (client as any).accessToken = "access-token";

      const chunks = [
        { text: "Chunk 1", metadata: {} },
        { text: "Chunk 2", metadata: {} },
      ];
      const documentId = "doc-id";
      const metadata = { key: "value" };
      const run_with_orchestration = true;

      const result = await client.ingestChunks(
        chunks,
        documentId,
        metadata,
        run_with_orchestration,
        undefined,
      );

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: "ingest_chunks",
        data: JSON.stringify({
          chunks,
          document_id: documentId,
          metadata,
          run_with_orchestration,
        }),
        headers: {
          Authorization: "Bearer access-token",
          "Content-Type": "application/json",
        },
        responseType: "json",
      });
    });

    test("updateChunk should send PUT request to /update_chunk/{documentId}/{extractionId} with correct data", async () => {
      const mockResponse = { success: true };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set accessToken
      (client as any).accessToken = "access-token";

      const documentId = "doc-id";
      const extractionId = "chunk-id";
      const text = "Updated text";
      const metadata = { key: "new value" };
      const runWithOrchestration = false;

      const result = await client.updateChunk(
        documentId,
        extractionId,
        text,
        metadata,
        runWithOrchestration,
      );

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "PUT",
        url: `update_chunk/${documentId}/${extractionId}`,
        data: JSON.stringify({
          text,
          metadata,
          run_with_orchestration: runWithOrchestration,
        }),
        headers: {
          Authorization: "Bearer access-token",
          "Content-Type": "application/json",
        },
        responseType: "json",
      });
    });
  });

  describe("Management Methods", () => {
    test("serverStats should send GET request to /server_stats and return data", async () => {
      const mockResponse = { uptime: 12345 };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set accessToken
      (client as any).accessToken = "access-token";

      const result = await client.serverStats();

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "GET",
        url: "server_stats",
        headers: {
          Authorization: "Bearer access-token",
        },
        responseType: "json",
      });
    });

    test("updatePrompt should send POST request to /update_prompt with correct data", async () => {
      const mockResponse = { success: true };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set accessToken
      (client as any).accessToken = "access-token";

      const name = "default_system";
      const template = "New template";
      const input_types = { key: "value" };

      const result = await client.updatePrompt(name, template, input_types);

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: "update_prompt",
        data: JSON.stringify({
          name,
          template,
          input_types,
        }),
        headers: {
          Authorization: "Bearer access-token",
          "Content-Type": "application/json",
        },
        responseType: "json",
      });
    });

    test("analytics should send GET request to /analytics with correct params", async () => {
      const mockResponse = { data: [] };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set accessToken
      (client as any).accessToken = "access-token";

      const filter_criteria = { date: "2021-01-01" };
      const analysis_types = ["type1", "type2"];

      const result = await client.analytics(filter_criteria, analysis_types);

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith(
        expect.objectContaining({
          method: "GET",
          url: "analytics",
          params: {
            filter_criteria: JSON.stringify(filter_criteria),
            analysis_types: JSON.stringify(analysis_types),
          },
          headers: {
            Authorization: "Bearer access-token",
          },
          responseType: "json",
        }),
      );
    });
  });

  describe("Retrieval Methods", () => {
    test("search should send POST request to /search with correct data", async () => {
      const mockResponse = { results: [] };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set accessToken
      (client as any).accessToken = "access-token";

      const query = "test query";
      const vector_search_settings = { top_k: 5 };
      const kg_search_settings = { max_hops: 2 };

      const result = await client.search(
        query,
        vector_search_settings,
        kg_search_settings,
      );

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: "search",
        data: JSON.stringify({
          query,
          vector_search_settings,
          kg_search_settings,
        }),
        headers: {
          Authorization: "Bearer access-token",
          "Content-Type": "application/json",
        },
        responseType: "json",
      });
    });

    test("rag should send POST request to /rag with correct data", async () => {
      const mockResponse = { answer: "Test answer" };
      mockAxiosInstance.request.mockResolvedValue({ data: mockResponse });

      // Set accessToken
      (client as any).accessToken = "access-token";

      const query = "test query";
      const rag_generation_config = { max_tokens: 100 };
      const vector_search_settings = { top_k: 5 };
      const kg_search_settings = { max_hops: 2 };
      const task_prompt_override = "Custom prompt";
      const include_title_if_available = true;

      const result = await client.rag(
        query,
        vector_search_settings,
        kg_search_settings,
        rag_generation_config,
        task_prompt_override,
        include_title_if_available,
      );

      expect(result).toEqual(mockResponse);
      expect(mockAxiosInstance.request).toHaveBeenCalledWith({
        method: "POST",
        url: "rag",
        data: JSON.stringify({
          query,
          vector_search_settings,
          kg_search_settings,
          rag_generation_config,
          task_prompt_override,
          include_title_if_available,
        }),
        headers: {
          Authorization: "Bearer access-token",
          "Content-Type": "application/json",
        },
        responseType: "json",
      });
    });
  });
});
