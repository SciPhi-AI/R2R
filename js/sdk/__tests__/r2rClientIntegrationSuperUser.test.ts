import { r2rClient } from "../src/index";
const fs = require("fs");

const baseUrl = "http://localhost:8000";

/**
 * raskolnikov.txt should have an id of `f9f61fc8-079c-52d0-910a-c657958e385b`
 * karamozov.txt should have an id of `73749580-1ade-50c6-8fbe-a5e9e87783c8`
 * myshkin.txt should have an id of `2e05b285-2746-5778-9e4a-e293db92f3be`
 */

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
        document_ids: ["2e05b285-2746-5778-9e4a-e293db92f3be"],
        metadatas: [{ title: "updated_karamozov.txt" }],
      }),
    ).resolves.not.toThrow();
  });

  test("Search documents", async () => {
    await expect(client.search("test")).resolves.not.toThrow();
  });

  test("Generate RAG response with additional parameters", async () => {
    await expect(
      client.rag(
        "test",
        { use_vector_search: true, search_limit: 5 },
        { use_kg_search: false },
        { temperature: 0.7 },
      ),
    ).resolves.not.toThrow();
  }, 30000);

  test("Agentic RAG response", async () => {
    const messages = [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "Tell me about Raskolnikov." },
    ];

    await expect(client.agent(messages)).resolves.not.toThrow();
  }, 30000);

  test("Score completion", async () => {
    const message_id = "906bb0a8-e6f6-5474-a5d4-7d7f28937f41";
    const score = 0.5;

    await expect(
      client.scoreCompletion(message_id, score),
    ).resolves.not.toThrow();
  });

  // TOOD: Fix in R2R, table logs has no column named run_id
  // test("Agentic RAG response with streaming", async () => {
  //   const messages = [
  //     { role: "system", content: "You are a helpful assistant." },
  //     { role: "user", content: "Tell me about Raskolnikov." },
  //   ];

  //   const stream = await client.agent(messages, undefined, undefined, {
  //     stream: true,
  //   });

  //   expect(stream).toBeDefined();

  //   let fullResponse = "";

  //   for await (const chunk of stream) {
  //     fullResponse += chunk;
  //   }

  //   expect(fullResponse.length).toBeGreaterThan(0);
  // }, 30000);

  // Deletes raskolnikov.txt
  test("Delete document", async () => {
    await expect(
      client.delete({
        document_id: "f9f61fc8-079c-52d0-910a-c657958e385b",
      }),
    ).resolves.toBe("");
  });

  test("Get logs", async () => {
    await expect(client.logs()).resolves.not.toThrow();
  });

  test("App settings", async () => {
    await expect(client.appSettings()).resolves.not.toThrow();
  });

  test("Get analytics", async () => {
    const filterCriteria: Record<string, any> | string = {
      search_latencies: "search_latency",
    };

    const analysisTypes: Record<string, any> | string = {
      search_latencies: ["basic_statistics", "search_latency"],
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
      client.documentChunks("73749580-1ade-50c6-8fbe-a5e9e87783c8"),
    ).resolves.not.toThrow();
  });

  test("Clean up remaining documents", async () => {
    // Deletes karamozov.txt
    await expect(
      client.delete({ document_id: "73749580-1ade-50c6-8fbe-a5e9e87783c8" }),
    ).resolves.toBe("");

    // Deletes myshkin.txt
    await expect(
      client.delete({ document_id: "2e05b285-2746-5778-9e4a-e293db92f3be" }),
    ).resolves.toBe("");
  });

  test("Logout", async () => {
    await expect(client.logout()).resolves.not.toThrow();
  });
});
