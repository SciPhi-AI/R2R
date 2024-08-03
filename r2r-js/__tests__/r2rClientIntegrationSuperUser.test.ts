import { r2rClient } from "../src/index";
import { FilterCriteria, AnalysisTypes } from "../src/models";
const fs = require("fs");

const baseUrl = "http://localhost:8000";

describe("r2rClient Integration Tests", () => {
  let client: r2rClient;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
  });

  test("Health check", async () => {
    await expect(client.health()).resolves.not.toThrow();
  });

  test("Login", async () => {
    await expect(
      client.login("admin@example.com", "change_me_immediately"),
    ).resolves.not.toThrow();
  });

  test("Server stats", async () => {
    await expect(client.serverStats()).resolves.not.toThrow();
  });

  test("Ingest file", async () => {
    const files = [
      { path: "examples/data/raskolnikov.txt", name: "raskolnikov.txt" },
    ];

    await expect(
      client.ingestFiles(files, {
        metadatas: [{ title: "raskolnikov.txt" }, { title: "karamozov.txt" }],
        user_ids: ["123e4567-e89b-12d3-a456-426614174000"],
        skip_document_info: false,
      }),
    ).resolves.not.toThrow();
  });

  test("Ingest files in folder", async () => {
    const files = ["examples/data/folder"];

    await expect(client.ingestFiles(files)).resolves.not.toThrow();
  });

  test("Update files", async () => {
    const updated_file = [
      { path: "examples/data/folder/myshkin.txt", name: "super_myshkin.txt" },
    ];
    await expect(
      client.updateFiles(updated_file, {
        document_ids: ["f3c6afa5-fc58-58b7-b797-f7148e5253c3"],
        metadatas: [{ title: "updated_karamozov.txt" }],
      }),
    ).resolves.not.toThrow();
  });

  test("Search documents", async () => {
    await expect(client.search("test")).resolves.not.toThrow();
  });

  test("Generate RAG response", async () => {
    await expect(client.rag({ query: "test" })).resolves.not.toThrow();
  }, 30000);

  test("Generate RAG Chat response", async () => {
    const messages = [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "Tell me about Raskolnikov." },
    ];

    await expect(client.agent({ messages })).resolves.not.toThrow();
  }, 30000);

  test("Generate RAG Chat response with streaming", async () => {
    const messages = [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "Tell me about Raskolnikov." },
    ];

    const streamingConfig = {
      messages,
      rag_generation_config: { stream: true },
    };

    const stream = await client.agent(streamingConfig);

    expect(stream).toBeDefined();
    expect(stream instanceof ReadableStream).toBe(true);

    let fullResponse = "";
    const reader = stream.getReader();

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }

      const chunk = new TextDecoder().decode(value);
      fullResponse += chunk;
    }

    expect(fullResponse.length).toBeGreaterThan(0);
  }, 30000);

  test("Delete document", async () => {
    await expect(
      client.delete(["document_id"], ["cb6e55f3-cb3e-5646-ad52-42f06eb321f5"]),
    ).resolves.not.toThrow();
  });

  test("Get logs", async () => {
    await expect(client.logs()).resolves.not.toThrow();
  });

  test("App settings", async () => {
    await expect(client.appSettings()).resolves.not.toThrow();
  });

  test("Get analytics", async () => {
    const filterCriteria: FilterCriteria = {
      filters: {
        search_latencies: "search_latency",
      },
    };

    const analysisTypes: AnalysisTypes = {
      analysis_types: {
        search_latencies: ["basic_statistics", "search_latency"],
      },
    };

    await expect(
      client.analytics(filterCriteria, analysisTypes),
    ).resolves.not.toThrow();
  });

  test("Get users overview", async () => {
    await expect(client.usersOverview()).resolves.not.toThrow();
  });

  test("Get documents overview", async () => {
    await expect(client.documentsOverview()).resolves.not.toThrow();
  });

  test("Get document chunks", async () => {
    await expect(
      client.documentChunks("43eebf9c-c2b4-59e5-993a-054bf4a5c423"),
    ).resolves.not.toThrow();
  });

  test("Clean up remaining documents", async () => {
    await expect(
      client.delete(["document_id"], ["43eebf9c-c2b4-59e5-993a-054bf4a5c423"]),
    ).resolves.not.toThrow();

    await expect(
      client.delete(["document_id"], ["f3c6afa5-fc58-58b7-b797-f7148e5253c3"]),
    ).resolves.not.toThrow;
  });

  test("Logout", async () => {
    await expect(client.logout()).resolves.not.toThrow();
  });
});
