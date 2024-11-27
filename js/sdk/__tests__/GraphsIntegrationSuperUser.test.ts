import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let documentId: string;
  let collectionId: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.users.login({
      email: "admin@example.com",
      password: "change_me_immediately",
    });
  });

  test("Create document with file path", async () => {
    const response = await client.documents.create({
      file: {
        path: "examples/data/raskolnikov_2.txt",
        name: "raskolnikov_2.txt",
      },
      metadata: { title: "raskolnikov_2.txt" },
    });

    expect(response.results.document_id).toBeDefined();
    documentId = response.results.document_id;
  }, 10000);

  test("Create new collection", async () => {
    const response = await client.collections.create({
      name: "Raskolnikov Collection",
    });
    expect(response).toBeTruthy();
    collectionId = response.results.id;
  });

  test("Retrieve collection", async () => {
    const response = await client.collections.retrieve({
      id: collectionId,
    });
    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(collectionId);
    expect(response.results.name).toBe("Raskolnikov Collection");
  });

  test("Update graph", async () => {
    const response = await client.graphs.update({
      collectionId: collectionId,
      name: "Raskolnikov Graph",
    });

    expect(response.results).toBeDefined();
  });

  test("Retrieve graph and ensure that update was successful", async () => {
    const response = await client.graphs.retrieve({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.name).toBe("Raskolnikov Graph");
    expect(response.results.updated_at).not.toBe(response.results.created_at);
  });

  test("List graphs", async () => {
    const response = await client.graphs.list({});

    expect(response.results).toBeDefined();
  });

  test("Check that there are no entities in the graph", async () => {
    const response = await client.graphs.listEntities({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength(0);
  });

  test("Check that there are no relationships in the graph", async () => {
    const response = await client.graphs.listRelationships({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength;
  });

  test("Extract entities from the document", async () => {
    const response = await client.documents.extract({
      id: documentId,
    });

    await new Promise((resolve) => setTimeout(resolve, 30000));

    expect(response.results).toBeDefined();
  }, 40000);

  test("Assign document to collection", async () => {
    const response = await client.collections.addDocument({
      id: collectionId,
      documentId: documentId,
    });
    expect(response.results).toBeDefined();
  });

  test("Pull entities into the graph", async () => {
    const response = await client.graphs.pull({
      collectionId: collectionId,
    });
    console.log("Pull entities into the graph", response.results);
    expect(response.results).toBeDefined();
  });

  test("Check that there are entities in the graph", async () => {
    const response = await client.graphs.listEntities({
      collectionId: collectionId,
    });
    expect(response.results).toBeDefined();
    expect(response.total_entries).toBeGreaterThanOrEqual(1);
  });

  test("Check that there are relationships in the graph", async () => {
    const response = await client.graphs.listRelationships({
      collectionId: collectionId,
    });
    expect(response.results).toBeDefined();
  });

  test("Reset the graph", async () => {
    const response = await client.graphs.reset({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
  });

  test("Check that there are no entities in the graph", async () => {
    const response = await client.graphs.listEntities({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength(0);
  });

  test("Check that there are no relationships in the graph", async () => {
    const response = await client.graphs.listRelationships({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength(0);
  });

  test("Delete raskolnikov_2.txt", async () => {
    const response = await client.documents.delete({
      id: documentId,
    });

    expect(response.results).toBeDefined();
  });

  test("Check that the document is not in the collection", async () => {
    const response = await client.collections.listDocuments({
      id: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength(0);
  });

  test("Delete Raskolnikov Collection", async () => {
    const response = await client.collections.delete({
      id: collectionId,
    });

    expect(response.results).toBeDefined();
  });
});
