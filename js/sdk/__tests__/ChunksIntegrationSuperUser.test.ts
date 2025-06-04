import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let documentId: string;
  let chunkId: string;
  let collectionId: string;

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

  test("Create a document assigned to a new collection", async () => {
    const collectionResponse = await client.collections.create({
      name: "Test Collection",
      description: "A collection for testing purposes",
    });
    collectionId = collectionResponse.results.id;
    console.log("Collection ID:", collectionId);

    const documentResponse = await client.documents.create({
      chunks: ["This is a test document."],
      collectionIds: [collectionId],
    });
    documentId = documentResponse.results.documentId;
    expect(documentResponse.results.documentId).toBeDefined();
    expect(documentResponse.results.message).toBe(
      "Document created and ingested successfully.",
    );
    expect(documentResponse.results.taskId).toBeNull();
  });

  test("Retrieve a document assigned to a collection", async () => {
    const response = await client.documents.list({});

    console.log(response.results);

    expect(response.results).toBeDefined();
    expect(response.results.length).toBeGreaterThan(0);
    expect(response.results[0].collectionIds).toContain(collectionId);
  });

  test("Delete the collection", async () => {
    const response = await client.collections.delete({
      id: collectionId,
    });
    expect(response.results.success).toBe(true);
  });

  test("Delete the document created in the collection", async () => {
    const response = await client.documents.delete({
      id: documentId,
    });
    expect(response.results.success).toBe(true);
  });

  // test("Delete a chunk that does not exist", async () => {
  //   await expect(client.chunks.delete({ id: chunkId })).rejects.toThrow(
  //     /Status 404/,
  //   );
  // });
});
