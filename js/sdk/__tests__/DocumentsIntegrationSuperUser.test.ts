import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect, afterAll } from "@jest/globals";
import fs from "fs";
import path from "path";

const baseUrl = "http://localhost:7272";
const TEST_OUTPUT_DIR = path.join(__dirname, "test-output");

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

    if (!fs.existsSync(TEST_OUTPUT_DIR)) {
      fs.mkdirSync(TEST_OUTPUT_DIR);
    }
  });

  afterAll(() => {
    if (fs.existsSync(TEST_OUTPUT_DIR)) {
      fs.rmSync(TEST_OUTPUT_DIR, { recursive: true, force: true });
    }
  });

  test("Create document with file path", async () => {
    const response = await client.documents.create({
      file: { path: "examples/data/marmeladov.txt", name: "marmeladov.txt" },
      metadata: { title: "marmeladov.txt" },
    });

    expect(response.results.documentId).toBeDefined();
    documentId = response.results.documentId;
  }, 10000);

  test("Create document with content", async () => {
    const response = await client.documents.create({
      raw_text: "This is a test document",
      metadata: { title: "Test Document" },
    });

    expect(response.results.documentId).toBeDefined();
  }, 30000);

  test("Retrieve document", async () => {
    const response = await client.documents.retrieve({
      id: documentId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(documentId);
    expect(response.results.collectionIds).toContain(
      "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
    );
    expect(response.results.metadata.title).toBe("marmeladov.txt");
    expect(response.results.sizeInBytes).toBeDefined();
    expect(response.results.ingestionStatus).toBe("success");
    expect(response.results.extractionStatus).toBe("pending");
    expect(response.results.createdAt).toBeDefined();
    expect(response.results.updatedAt).toBeDefined();
    expect(response.results.summary).toBeDefined();
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

  test("Export documents to CSV with default options", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "documents_default.csv");
    await client.documents.export({ outputPath });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
    expect(content.split("\n").length).toBeGreaterThan(1);
  });

  test("Export documents to CSV with custom columns", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "documents_custom.csv");
    await client.documents.export({
      outputPath,
      columns: ["id", "title", "created_at"],
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    const headers = content
      .split("\n")[0]
      .split(",")
      .map((h) => h.trim());

    expect(headers).toContain('"id"');
    expect(headers).toContain('"title"');
    expect(headers).toContain('"created_at"');
  });

  test("Export filtered documents to CSV", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "documents_filtered.csv");
    await client.documents.export({
      outputPath,
      filters: { document_type: { $eq: "txt" } },
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
  });

  test("Export documents without headers", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "documents_no_header.csv");
    await client.documents.export({
      outputPath,
      includeHeader: false,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
  });

  test("Handle empty export result", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "documents_empty.csv");
    await client.documents.export({
      outputPath,
      filters: { type: { $eq: "non_existent_type" } },
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content.split("\n").filter((line) => line.trim()).length).toBe(1);
  });

  test("Error handling - Create document with no file or content", async () => {
    await expect(
      client.documents.create({
        metadata: { title: "No Content" },
      }),
    ).rejects.toThrow(/Either file, raw_text, or chunks must be provided/);
  });

  test("Error handling - Create document with both file and content", async () => {
    await expect(
      client.documents.create({
        file: {
          path: "examples/data/raskolnikov.txt",
          name: "raskolnikov.txt",
        },
        raw_text: "Test content",
        metadata: { title: "Both File and Content" },
      }),
    ).rejects.toThrow(/Only one of file, raw_text, or chunks may be provided/);
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
