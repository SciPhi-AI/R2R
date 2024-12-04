import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let document_id: string;
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

    document_id = response.results.document_id;

    expect(response.results).toEqual({
      document_id: expect.any(String),
      message: "Document created and ingested successfully.",
      task_id: null,
    });
  });

  test("Retrieve document's chunks", async () => {
    const response = await client.documents.listChunks({
      id: document_id,
    });

    chunkId = response.results[0]?.id;

    expect(chunkId).toBeDefined();
    expect(response.results[0]).toMatchObject({
      id: expect.any(String),
      document_id: expect.any(String),
      text: expect.any(String),
      collection_ids: expect.any(Array),
      metadata: expect.any(Object),
    });
  });

  test("Retrieve a chunk", async () => {
    const response = await client.chunks.retrieve({
      id: chunkId,
    });

    expect(response.results).toMatchObject({
      id: expect.any(String),
      document_id: expect.any(String),
      text: expect.any(String),
      collection_ids: expect.any(Array),
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
      document_id: expect.any(String),
      text: "Hello, world! How are you?",
      collection_ids: expect.any(Array),
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

  // test("Delete a chunk that does not exist", async () => {
  //   await expect(client.chunks.delete({ id: chunkId })).rejects.toThrow(
  //     /Status 404/,
  //   );
  // });
});
