import { r2rClient } from "../src/index";
const fs = require("fs");
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

/**
 * Test Collection should have a UUID of `6f2a5494-f759-4f12-a7b6-db836f651577`
 */
describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let collectionId: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.login("admin@example.com", "change_me_immediately");
  });

  test("Create new collection", async () => {
    const response = await client.collections.create("Test Collection");
    expect(response).toBeTruthy();
    collectionId = response.results.collection_id; // Updated to use correct path
  });

  test("Delete collection", async () => {
    await expect(client.collections.delete(collectionId)).resolves.toBeTruthy();
  });

  //   test("Create document with content", async () => {
  //     const response = await client.documents.create({
  //       content: "This is a test document",
  //       metadata: { title: "Test Document" },
  //     });

  //     expect(response.results.document_id).toBeDefined();
  //   });

  // test("Update document", async () => {
  //   const response = await client.documents.update({
  //     id: documentId,
  //     content: "Updated content",
  //     metadata: { title: "Updated Test Document" },
  //   });

  //   expect(response.results).toBeDefined();
  // });

  //   test("Retrieve document", async () => {
  //     const response = await client.documents.retrieve(documentId);

  //     expect(response.results).toBeDefined();
  //     expect(response.results.id).toBe(documentId);
  //   });

  //   test("List documents with no parameters", async () => {
  //     const response = await client.documents.list();

  //     expect(response.results).toBeDefined();
  //     expect(Array.isArray(response.results)).toBe(true);
  //   });

  //   test("List documents with parameters", async () => {
  //     const response = await client.documents.list({
  //       offset: 0,
  //       limit: 5,
  //     });

  //     expect(response.results).toBeDefined();
  //     expect(Array.isArray(response.results)).toBe(true);
  //     expect(response.results.length).toBeLessThanOrEqual(5);
  //   });

  //   test("Error handling - Create document with no file or content", async () => {
  //     await expect(
  //       client.documents.create({
  //         metadata: { title: "No Content" },
  //       }),
  //     ).rejects.toThrow(/Either file.*or content must be provided/);
  //   });

  //   test("Error handling - Create document with both file and content", async () => {
  //     await expect(
  //       client.documents.create({
  //         file: {
  //           path: "examples/data/raskolnikov.txt",
  //           name: "raskolnikov.txt",
  //         },
  //         content: "Test content",
  //         metadata: { title: "Both File and Content" },
  //       }),
  //     ).rejects.toThrow(/Cannot provide both file.*and content/);
  //   });

  //   test("Delete Raskolnikov.txt", async () => {
  //     const response = await client.documents.delete("f9f61fc8-079c-52d0-910a-c657958e385b");

  //     expect(response.results).toBeDefined();
  //   });

  //   test("Delete untitled document", async () => {
  //     const response = await client.documents.delete("5556836e-a51c-57c7-916a-de76c79df2b6");

  //     expect(response.results).toBeDefined();
  //   });
});
