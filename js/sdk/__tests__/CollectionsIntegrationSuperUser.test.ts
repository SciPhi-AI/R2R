import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

/**
 * zametov.txt will have an id of 69100f1e-2839-5b37-916d-5c87afe14094
 */
describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let collectionId: string;
  let documentId: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.users.login({
      email: "admin@example.com",
      password: "change_me_immediately",
    });
  });

  test("Create new collection", async () => {
    const response = await client.collections.create({
      name: "Test Collection",
    });
    expect(response).toBeTruthy();
    collectionId = response.results.id;
  });

  test("List collections", async () => {
    const response = await client.collections.list();
    expect(response.results).toBeDefined();
  });

  test("Retrieve collection", async () => {
    const response = await client.collections.retrieve({ id: collectionId });
    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(collectionId);
    expect(response.results.name).toBe("Test Collection");
    expect(response.results.description).toBeNull();
  });

  test("Update collection", async () => {
    const response = await client.collections.update({
      id: collectionId,
      name: "Updated Test Collection",
      generateDescription: true,
    });
    expect(response.results).toBeDefined();
  }, 10000);

  test("Retrieve updated collection", async () => {
    const response = await client.collections.retrieve({ id: collectionId });
    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(collectionId);
    expect(response.results.name).toBe("Updated Test Collection");
    expect(response.results.description).toBeDefined();
  });

  test("Ingest document and assign to collection", async () => {
    const ingestResponse = await client.documents.create({
      file: { path: "examples/data/zametov.txt", name: "zametov.txt" },
      metadata: { title: "zametov.txt" },
    });

    expect(ingestResponse.results.documentId).toBeDefined();
    documentId = ingestResponse.results.documentId;

    const response = await client.collections.addDocument({
      id: collectionId,
      documentId: documentId,
    });

    expect(response.results).toBeDefined();
  }, 10000);

  test("List documents in collection", async () => {
    const response = await client.collections.listDocuments({
      id: collectionId,
    });
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

  test("Delete zametov.txt", async () => {
    const response = await client.documents.delete({
      id: "69100f1e-2839-5b37-916d-5c87afe14094",
    });

    expect(response.results).toBeDefined();
  });

  test("Delete collection", async () => {
    await expect(
      client.collections.delete({ id: collectionId }),
    ).resolves.toBeTruthy();
  });
});
