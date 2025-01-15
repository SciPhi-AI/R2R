import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect, afterAll } from "@jest/globals";
import fs from "fs";
import path from "path";
const TEST_OUTPUT_DIR = path.join(__dirname, "test-output");

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

    if (!fs.existsSync(TEST_OUTPUT_DIR)) {
      fs.mkdirSync(TEST_OUTPUT_DIR);
    }
  });

  afterAll(() => {
    if (fs.existsSync(TEST_OUTPUT_DIR)) {
      fs.rmSync(TEST_OUTPUT_DIR, { recursive: true, force: true });
    }
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

  test("Export collections to CSV with default options", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "collections_default.csv");
    await client.collections.export({ outputPath: outputPath });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
    expect(content.split("\n").length).toBeGreaterThan(1);
  });

  test("Export documents to CSV with custom columns", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "collections_custom.csv");
    await client.collections.export({
      outputPath: outputPath,
      columns: ["id", "name", "created_at"],
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    const headers = content
      .split("\n")[0]
      .split(",")
      .map((h) => h.trim());

    expect(headers).toContain('"id"');
    expect(headers).toContain('"name"');
    expect(headers).toContain('"created_at"');
  });

  test("Export filtered collections to CSV", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "collections_filtered.csv");
    await client.collections.export({
      outputPath: outputPath,
      filters: { id: { $eq: collectionId } },
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
  });

  test("Export collections without headers", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "collections_no_header.csv");
    await client.collections.export({
      outputPath: outputPath,
      includeHeader: false,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
  });

  test("Handle empty export result", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "collections_empty.csv");
    await client.collections.export({
      outputPath: outputPath,
      filters: { name: { $eq: "non_existent_name" } },
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content.split("\n").filter((line) => line.trim()).length).toBe(1);
  });

  test("Remove document from collection", async () => {
    const response = await client.collections.removeDocument({
      id: collectionId,
      documentId: documentId,
    });

    expect(response.results).toBeDefined();
  });

  test("Retrieve a collection with no documents", async () => {
    const response = await client.collections.retrieve({ id: collectionId });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(collectionId);
    expect(response.results.name).toBe("Updated Test Collection");
    expect(response.results.description).toBeDefined();
    expect(response.results.documentCount).toBe(0);
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
