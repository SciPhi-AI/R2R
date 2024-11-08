import { r2rClient } from "../src/index";
const fs = require("fs");
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let collectionId: string;
  let documentId: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.login("admin@example.com", "change_me_immediately");
  });

  test("Create new collection", async () => {
    const response = await client.collections.create({
      name: "Test Collection",
    });
    expect(response).toBeTruthy();
    collectionId = response.results.collection_id;
  });

  test("List collections", async () => {
    const response = await client.collections.list();
    console.log("List collections response: ", response);
    expect(response.results).toBeDefined();
  });

  test("Retrieve collection", async () => {
    const response = await client.collections.retrieve({ id: collectionId });
    expect(response.results).toBeDefined();
  });

  test("Update collection", async () => {
    const response = await client.collections.update({
      id: collectionId,
      name: "Updated Test Collection",
    });
    expect(response.results).toBeDefined();
  });

  test("Ingest document and assign to collection", async () => {
    const ingestResponse = await client.documents.create({
      file: { path: "examples/data/zametov.txt", name: "zametov.txt" },
      metadata: { title: "zametov.txt" },
    });

    expect(ingestResponse.results.document_id).toBeDefined();
    documentId = ingestResponse.results.document_id;

    const response = await client.collections.addDocument({
      id: collectionId,
      documentId: documentId,
    });

    expect(response.results).toBeDefined();
  });

  test("List documents in collection", async () => {
    const response = await client.collections.listDocuments({
      id: collectionId,
    });
    console.log("List documents in collection response: ", response);
    expect(response.results).toBeDefined();
  });

  // TODO: Need to implement user methods in V3
  // test("Add user to collection", async () => {
  //   const response = await client.collections.addUser({
  //     id: collectionId,
  //     userId: "",
  //   });
  //   expect(response.results).toBeDefined
  // });

  test("List users in collection", async () => {
    const response = await client.collections.listUsers({ id: collectionId });
    console.log("List users in collection response: ", response);
    expect(response.results).toBeDefined();
  });

  // TODO: Need to implement user methods in V3
  // test("Remove user from collection", async () => {
  //   const response = await client.collections.removeUser({
  //     id: collectionId,
  //     userId: "",
  //   });
  //   expect(response.results).toBeDefined();
  // });

  test("Remove document from collection", async () => {
    const response = await client.collections.removeDocument({
      id: collectionId,
      documentId: documentId,
    });

    expect(response.results).toBeDefined();
  });

  test("Delete collection", async () => {
    await expect(
      client.collections.delete({ id: collectionId }),
    ).resolves.toBeTruthy();
  });
});
