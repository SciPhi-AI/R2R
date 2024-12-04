import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

/**
 * marmeladov.txt will have an id of 83ef5342-4275-5b75-92d6-692fa32f8523
 * The untitled document will have an id of 5556836e-a51c-57c7-916a-de76c79df2b6
 */
describe("r2rClient V3 Documents Integration Tests", () => {
  let client: r2rClient;
  let documentId: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.users.login({
      email: "admin@example.com",
      password: "change_me_immediately",
    });
  });

  test("Create document with file path", async () => {
    const response = await client.documents.create({
      file: { path: "examples/data/marmeladov.txt", name: "marmeladov.txt" },
      metadata: { title: "marmeladov.txt" },
    });

    expect(response.results.document_id).toBeDefined();
    documentId = response.results.document_id;
  }, 10000);

  test("Create document with content", async () => {
    const response = await client.documents.create({
      content: "This is a test document",
      metadata: { title: "Test Document" },
    });

    expect(response.results.document_id).toBeDefined();
  }, 30000);

  test("Retrieve document", async () => {
    const response = await client.documents.retrieve({
      id: documentId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(documentId);
  });

  test("List documents with no parameters", async () => {
    const response = await client.documents.list();

    expect(response.results).toBeDefined();
    expect(Array.isArray(response.results)).toBe(true);
  });

  test("List documents with parameters", async () => {
    const response = await client.documents.list({
      offset: 0,
      limit: 5,
    });

    expect(response.results).toBeDefined();
    expect(Array.isArray(response.results)).toBe(true);
    expect(response.results.length).toBeLessThanOrEqual(5);
  });

  test("Error handling - Create document with no file or content", async () => {
    await expect(
      client.documents.create({
        metadata: { title: "No Content" },
      }),
    ).rejects.toThrow(/Either file.*or content must be provided/);
  });

  test("Error handling - Create document with both file and content", async () => {
    await expect(
      client.documents.create({
        file: {
          path: "examples/data/raskolnikov.txt",
          name: "raskolnikov.txt",
        },
        content: "Test content",
        metadata: { title: "Both File and Content" },
      }),
    ).rejects.toThrow(/Cannot provide both file.*and content/);
  });

  test("Delete Raskolnikov.txt", async () => {
    const response = await client.documents.delete({
      id: "83ef5342-4275-5b75-92d6-692fa32f8523",
    });

    expect(response.results).toBeDefined();
  });

  test("Delete untitled document", async () => {
    const response = await client.documents.delete({
      id: "5556836e-a51c-57c7-916a-de76c79df2b6",
    });

    expect(response.results).toBeDefined();
  });
});
