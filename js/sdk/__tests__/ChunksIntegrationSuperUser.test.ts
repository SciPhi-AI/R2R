import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.users.login({
      email: "admin@example.com",
      password: "change_me_immediately",
    });
  });

  test("Create a chunk", async () => {
    const response = await client.chunks.create({
      chunks: [
        {
          id: "a285d6ff-1219-4315-a7d4-649b300af992",
          document_id: "a285d6ff-1219-4315-a7d4-649b300af992",
          collection_ids: [],
          metadata: { key: "value" },
          text: "Hello, world!",
        },
      ],
      runWithOrchestration: false,
    });

    expect(response.results).toEqual([
      {
        document_id: expect.any(String),
        message: "Document created and ingested successfully.",
      },
    ]);
  }, 10000);

  test("Retrieve a chunk", async () => {
    const response = await client.chunks.retrieve({
      id: "a285d6ff-1219-4315-a7d4-649b300af992",
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
      id: "a285d6ff-1219-4315-a7d4-649b300af992",
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
      id: "a285d6ff-1219-4315-a7d4-649b300af992",
    });

    expect(response.results.text).toBe("Hello, world! How are you?");
  });

  test("List chunks", async () => {
    const response = await client.chunks.list();
    expect(response.results).toBeDefined();
  });

  test("Delete a chunk", async () => {
    const response = await client.chunks.delete({
      id: "a285d6ff-1219-4315-a7d4-649b300af992",
    });
    expect(response.results.success).toBe(true);
  });

  test("Delete a chunk that does not exist", async () => {
    await expect(
      client.chunks.delete({ id: "a285d6ff-1219-4315-a7d4-649b300af992" }),
    ).rejects.toThrow(/Status 404/);
  });
});
