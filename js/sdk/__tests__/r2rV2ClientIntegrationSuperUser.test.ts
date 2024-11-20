import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";
let newCollectionId: string;

/**
 * raskolnikov.txt should have an id of `f9f61fc8-079c-52d0-910a-c657958e385b`
 * karamozov.txt should have an id of `73749580-1ade-50c6-8fbe-a5e9e87783c8`
 * myshkin.txt should have an id of `2e05b285-2746-5778-9e4a-e293db92f3be`
 * The first ingested chunk should have an id of `731030c6-9244-5cfc-a9fd-81e4eb356cd3`
 * The second ingested chunk should have an id of `bd2cbead-66e0-57bc-acea-2c34711a39b5`
 * The default collection should have an id of `122fdf6a-e116-546b-a8f6-e4cb2e2c0a09`
 */

/**
 * Coverage
 *     - health
 *    Auth:
 *     X register
 *     X verifyEmail
 *     - login
 *     - logout
 *     - user
 *     X updateUser
 *     - refreshAccessToken
 *     X changePassword
 *     - requestPasswordReset
 *     X confirmPasswordReset
 *     X deleteUser
 *    Ingestion:
 *     - ingestFiles
 *     - updateFiles
 *     - ingestChunks
 *     - updateChunks
 *     X createVectorIndex
 *     X listVectorIndices
 *     X deleteVectorIndex
 *    Management:
 *     - serverStats
 *     X updatePrompt
 *     X addPrompt
 *     X getPrompt
 *     X getAllPrompts
 *     X deletePrompt
 *     - analytics
 *     - logs
 *     - appSettings
 *     - usersOverview
 *     - delete
 *     X downloadFile
 *     - documentsOverview
 *     - documentChunks
 *     X collectionsOverview
 *     - createCollection
 *     - getCollection
 *     - updateCollection
 *     - deleteCollection
 *     - listCollections
 *     X addUserToCollection
 *     X removeUserFromCollection
 *     - getUsersInCollection
 *     X getCollectionsForUser
 *     X assignDocumentToCollection
 *     X removeDocumentFromCollection
 *     X getDocumentCollections
 *     X getDocumentsInCollection
 *     - conversationsOverview
 *     - getConversation
 *     - createConversation
 *     - addMessage
 *     X updateMessage
 *     X updateMessageMetadata
 *     X branchesOverview
 *     X getNextBranch
 *     X getPreviousBranch
 *     X branchAtMessage
 *     - deleteConversation
 *    Knowledge Graphs:
 *     X createGraph
 *     X enrichGraph
 *     X getEntities
 *     X getRelationships
 *     X getCommunities
 *     X getTunedPrompt
 *     X deduplicateEntities
 *     X deleteGraphForCollection
 *    Retrieval:
 *     - search
 *     - rag
 *     X streamingRag
 *     - agent
 *     X streamingAgent
 */

describe("r2rClient Integration Tests", () => {
  let client: r2rClient;
  let createdConversationId: any;

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

  test("User", async () => {
    await expect(client.user()).resolves.not.toThrow();
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
  }, 10000);

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

  test("Ingest chunks with no id or metadata", async () => {
    await expect(
      client.ingestChunks([{ text: "test chunks" }]),
    ).resolves.not.toThrow();
  });

  test("Ingest chunks", async () => {
    await expect(
      client.ingestChunks(
        [{ text: "chunk 1" }, { text: "chunk 2" }],
        undefined,
        { source: "example" },
      ),
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

  test("Agentic RAG response with streaming", async () => {
    const messages = [
      { role: "system", content: "You are a helpful assistant." },
      { role: "user", content: "Tell me about Raskolnikov." },
    ];

    const stream = await client.agent(messages, { stream: true });

    expect(stream).toBeDefined();

    let fullResponse = "";

    if (stream && stream.getReader) {
      const reader = stream.getReader();
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }
        fullResponse += new TextDecoder().decode(value);
      }
    } else {
      throw new Error("Stream is not a ReadableStream");
    }

    expect(fullResponse.length).toBeGreaterThan(0);
  }, 30000);

  // Deletes raskolnikov.txt
  test("Delete document", async () => {
    await expect(
      client.delete({
        document_id: {
          $eq: "f9f61fc8-079c-52d0-910a-c657958e385b",
        },
      }),
    ).resolves.toBe("");
  });

  test("Get logs", async () => {
    await expect(client.logs()).resolves.not.toThrow();
  });

  test("App settings", async () => {
    await expect(client.appSettings()).resolves.not.toThrow();
  });

  test("Refresh access token", async () => {
    await expect(client.refreshAccessToken()).resolves.not.toThrow();
  });

  test("Request password reset", async () => {
    await expect(
      client.requestPasswordReset("admin@example.com"),
    ).resolves.not.toThrow();
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

  test("Update chunk", async () => {
    const response = await client.updateChunk(
      "bd2cbead-66e0-57bc-acea-2c34711a39b5",
      "c043aa2c-80e8-59ed-a390-54f1947ea32b",
      "updated text",
    );
  });

  // test("Ensure that updated chunk has updated text", async () => {
  //   const response = await client.documentChunks(
  //     "bd2cbead-66e0-57bc-acea-2c34711a39b5",
  //   );

  //   const targetId = "c043aa2c-80e8-59ed-a390-54f1947ea32b";
  //   const updatedChunk = response.results.find(
  //     (chunk: { chunk_id: string; text: string }) =>
  //       String(chunk.chunk_id) === targetId,
  //   );

  //   expect(updatedChunk).toBeDefined();
  //   expect(updatedChunk?.text).toBe("updated text");
  // });

  test("Delete the updated chunk", async () => {
    await expect(
      client.delete({
        chunk_id: {
          $eq: "c043aa2c-80e8-59ed-a390-54f1947ea32b",
        },
      }),
    ).resolves.toBe("");
  });

  test("Create collection", async () => {
    const response = await client.createCollection(
      "test_collection",
      "test_description",
    );
    newCollectionId = response.results.id;

    expect(newCollectionId).toBeDefined();
  });

  test("Get default collection", async () => {
    await expect(
      client.getCollection("122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"),
    ).resolves.not.toThrow();
  });

  test("Get newly created collection", async () => {
    await expect(client.getCollection(newCollectionId)).resolves.not.toThrow();
  });

  test("Update collection", async () => {
    await expect(
      client.updateCollection(
        newCollectionId,
        "updated_test_collection",
        "updated_test_description",
      ),
    ).resolves.not.toThrow();
  });

  test("List collections", async () => {
    await expect(client.listCollections()).resolves.not.toThrow();
  });

  test("Delete collection", async () => {
    await expect(
      client.deleteCollection(newCollectionId),
    ).resolves.not.toThrow();
  });

  test("Get users in collection", async () => {
    await expect(
      client.getUsersInCollection("122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"),
    ).resolves.not.toThrow();
  });

  test("Get users in collection with pagination", async () => {
    await expect(
      client.getUsersInCollection(
        "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
        10,
        10,
      ),
    ).resolves.not.toThrow();
  });

  test("Get conversations overview", async () => {
    await expect(client.conversationsOverview()).resolves.not.toThrow();
  });

  test("Create conversation", async () => {
    const createConversationResponse = await client.createConversation();
    createdConversationId = createConversationResponse.results.id;
    expect(createdConversationId).toBeDefined();
  });

  test("Get conversation", async () => {
    await expect(
      client.getConversation(createdConversationId),
    ).resolves.not.toThrow();
  });

  test("Add message to conversation", async () => {
    const message = {
      role: "user",
      content: "Hello, world!",
    };

    await expect(
      client.addMessage(createdConversationId, message),
    ).resolves.not.toThrow();
  });

  test("Branches overview", async () => {
    await expect(
      client.branchesOverview(createdConversationId),
    ).resolves.not.toThrow();
  });

  test("Delete conversation", async () => {
    await expect(
      client.deleteConversation(createdConversationId),
    ).resolves.not.toThrow();
  });

  test("Clean up remaining documents", async () => {
    // Deletes karamozov.txt
    await expect(
      client.delete({
        document_id: {
          $eq: "73749580-1ade-50c6-8fbe-a5e9e87783c8",
        },
      }),
    ).resolves.toBe("");

    // Deletes myshkin.txt
    await expect(
      client.delete({
        document_id: {
          $eq: "2e05b285-2746-5778-9e4a-e293db92f3be",
        },
      }),
    ).resolves.toBe("");

    // Deletes Ingested chunk 1
    await expect(
      client.delete({
        document_id: {
          $eq: "731030c6-9244-5cfc-a9fd-81e4eb356cd3",
        },
      }),
    ).resolves.toBe("");

    // Deletes Ingseted chunk 2
    await expect(
      client.delete({
        document_id: {
          $eq: "bd2cbead-66e0-57bc-acea-2c34711a39b5",
        },
      }),
    ).resolves.toBe("");
  });

  test("Logout", async () => {
    await expect(client.logout()).resolves.not.toThrow();
  });
});
