import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let documentId: string;
  let chunkId: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.users.login({
      email: "admin@example.com",
      password: "change_me_immediately",
    });
  });

  test("Create a chunk", async () => {
    const response = await client.documents.create({
      chunks: ["Hello, world!"],
      runWithOrchestration: false,
    });

    documentId = response.results.documentId;

    expect(response.results).toEqual({
      documentId: expect.any(String),
      message: "Document created and ingested successfully.",
      taskId: null,
    });
  });

  test("Create a document from chunks with an id", async () => {
    const response = await client.documents.create({
      id: "1fb70f3b-37eb-4325-8c83-694a03144a67",
      chunks: ["Hallo, Welt!"],
    });

    expect(response.results.documentId).toBe(
      "1fb70f3b-37eb-4325-8c83-694a03144a67",
    );
    expect(response.results.message).toBe(
      "Document created and ingested successfully.",
    );
    expect(response.results.taskId).toBeNull();
  });

  test("Retrieve document's chunks", async () => {
    const response = await client.documents.listChunks({
      id: documentId,
    });

    chunkId = response.results[0]?.id;

    expect(chunkId).toBeDefined();
    expect(response.results[0]).toMatchObject({
      id: expect.any(String),
      documentId: expect.any(String),
      text: expect.any(String),
      collectionIds: expect.any(Array),
      metadata: expect.any(Object),
    });
  });

  test("Retrieve a chunk", async () => {
    const response = await client.chunks.retrieve({
      id: chunkId,
    });

    expect(response.results).toMatchObject({
      id: expect.any(String),
      documentId: expect.any(String),
      text: expect.any(String),
      collectionIds: expect.any(Array),
      metadata: expect.any(Object),
    });
  });

  test("Update a chunk", async () => {
    const response = await client.chunks.update({
      id: chunkId,
      text: "Hello, world! How are you?",
    });

    expect(response.results).toMatchObject({
      id: expect.any(String),
      documentId: expect.any(String),
      text: "Hello, world! How are you?",
      collectionIds: expect.any(Array),
      metadata: expect.any(Object),
    });
  });

  test("Retrieve a chunk after update and check text", async () => {
    const response = await client.chunks.retrieve({
      id: chunkId,
    });

    expect(response.results.text).toBe("Hello, world! How are you?");
  });

  test("List chunks", async () => {
    const response = await client.chunks.list();
    expect(response.results).toBeDefined();
  });

  test("Delete a chunk", async () => {
    const response = await client.chunks.delete({
      id: chunkId,
    });
    expect(response.results.success).toBe(true);
  });

  test("Delete a document", async () => {
    const response = await client.documents.delete({
      id: "1fb70f3b-37eb-4325-8c83-694a03144a67",
    });
    expect(response.results.success).toBe(true);
  });

  // test("Delete a chunk that does not exist", async () => {
  //   await expect(client.chunks.delete({ id: chunkId })).rejects.toThrow(
  //     /Status 404/,
  //   );
  // });
});
