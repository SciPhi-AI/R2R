import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect, afterAll } from "@jest/globals";
import exp from "constants";
import fs from "fs";
import path from "path";

const baseUrl = "http://localhost:7272";
const TEST_OUTPUT_DIR = path.join(__dirname, "test-output");

/**
 * marmeladov.txt will have an id of 649d1072-7054-4e17-bd51-1af5f467d617
 * The untitled document will have an id of 5556836e-a51c-57c7-916a-de76c79df2b6
 * The default collection id is 122fdf6a-e116-546b-a8f6-e4cb2e2c0a09
 * The invalid JSON file will have an id of 04ebba11-8d7c-5e7e-ade8-8f02edee2327
 */
describe("r2rClient V3 Documents Integration Tests", () => {
  let client: r2rClient;
  let documentId: string;
  let documentId2: string;
  let documentId3: string;
  let documentId4: string;

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
      metadata: { title: "marmeladov.txt", numericId: 123 },
      id: "649d1072-7054-4e17-bd51-1af5f467d617",
    });

    expect(response.results.documentId).toBe(
      "649d1072-7054-4e17-bd51-1af5f467d617",
    );
    documentId = response.results.documentId;
  }, 10000);

  test("Create document with content", async () => {
    const response = await client.documents.create({
      raw_text: "This is a test document",
      metadata: { title: "Test Document", numericId: 456 },
    });

    expect(response.results.documentId).toBeDefined();
  }, 30000);

  test("Create a document with content that ends in a URL on a newline", async () => {
    const response = await client.documents.create({
      raw_text: "This is a test document\nhttps://example.com",
      metadata: { title: "Test Document with URL", numericId: 789 },
    });

    expect(response.results.documentId).toBeDefined();
    documentId2 = response.results.documentId;
  });

  test("Create a different document with the same URL on a newline", async () => {
    const response = await client.documents.create({
      raw_text: "This is a different test document\nhttps://example.com",
      metadata: { title: "Different Test Document with URL", numericId: 101 },
    });

    expect(response.results.documentId).toBeDefined();
    documentId3 = response.results.documentId;
  });

  test("Create a document in 'fast' ingestion mode", async () => {
    const response = await client.documents.create({
      raw_text: "A document with 'fast' ingestion mode.",
      ingestionMode: "fast",
    });

    expect(response.results.documentId).toBeDefined();
    documentId4 = response.results.documentId;
  });

  test("Create a document from an invalid JSON file", async () => {
    await expect(
      client.documents.create({
        file: { path: "examples/data/invalid.json", name: "invalid.json" },
        metadata: { title: "invalid.json" },
      }),
    ).rejects.toThrow(/Status 400/);
  });

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

  test("Append new metadata to document", async () => {
    const response = await client.documents.appendMetadata({
      id: documentId,
      metadata: [{ newfield: "new value" }, { newfield2: "new value 2" }],
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(documentId);
    expect(response.results.collectionIds).toContain(
      "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
    );
    expect(response.results.metadata.title).toBe("marmeladov.txt");
    expect(response.results.metadata.newfield).toBe("new value");
    expect(response.results.metadata.newfield2).toBe("new value 2");
    expect(response.results.sizeInBytes).toBeDefined();
    expect(response.results.ingestionStatus).toBe("success");
    expect(response.results.extractionStatus).toBe("pending");
    expect(response.results.createdAt).toBeDefined();
    expect(response.results.updatedAt).toBeDefined();
    expect(response.results.summary).toBeDefined();
  });

  test("Replace metadata of document", async () => {
    const response = await client.documents.replaceMetadata({
      id: documentId,
      metadata: [
        { replacedfield: "replaced value" },
        { replacedfield2: "replaced value 2" },
      ],
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(documentId);
    expect(response.results.collectionIds).toContain(
      "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
    );
    expect(Object.keys(response.results.metadata).length).toBe(2);
    expect(response.results.metadata.replacedfield).toBe("replaced value");
    expect(response.results.metadata.replacedfield2).toBe("replaced value 2");
    expect(response.results.sizeInBytes).toBeDefined();
    expect(response.results.ingestionStatus).toBe("success");
    expect(response.results.extractionStatus).toBe("pending");
    expect(response.results.createdAt).toBeDefined();
    expect(response.results.updatedAt).toBeDefined();
    expect(response.results.summary).toBeDefined();
  });

  test("Retrieve 'fast' ingestion document", async () => {
    const response = await client.documents.retrieve({
      id: documentId4,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(documentId4);
    expect(response.results.ingestionStatus).toBe("success");
    expect(response.results.extractionStatus).toBe("pending");
    expect(response.results.createdAt).toBeDefined();
    expect(response.results.updatedAt).toBeDefined();
    expect(response.results.summary).toBeNull();
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
    await client.documents.export({ outputPath: outputPath });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
    expect(content.split("\n").length).toBeGreaterThan(1);
  });

  test("Export documents to CSV with custom columns", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "documents_custom.csv");
    await client.documents.export({
      outputPath: outputPath,
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
      outputPath: outputPath,
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
      outputPath: outputPath,
      includeHeader: false,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
  });

  test("Handle empty export result", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "documents_empty.csv");
    await client.documents.export({
      outputPath: outputPath,
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

  test("Search with $lte filter should only return documents with numericId <= 200", async () => {
    const response = await client.retrieval.search({
      query: "Test query",
      searchSettings: {
        filters: {
          numericId: { $lte: 200 },
        },
      },
    });

    expect(response.results.chunkSearchResults).toBeDefined();
    expect(
      response.results.chunkSearchResults.every(
        (result) => result.metadata?.numericId <= 200,
      ),
    ).toBe(true);
  });

  test("Search with $gte filter should only return documents with metadata.numericId >= 400", async () => {
    const response = await client.retrieval.search({
      query: "Test query",
      searchSettings: {
        filters: {
          "metadata.numericId": { $gte: 400 },
        },
      },
    });

    expect(response.results.chunkSearchResults).toBeDefined();
    expect(
      response.results.chunkSearchResults.every(
        (result) => result.metadata?.numericId >= 400,
      ),
    ).toBe(true);
  });

  test("Search with $eq filter should only return exact matches", async () => {
    const response = await client.retrieval.search({
      query: "Test query",
      searchSettings: {
        filters: {
          numericId: { $eq: 123 },
        },
      },
    });

    expect(response.results.chunkSearchResults).toBeDefined();
    expect(
      response.results.chunkSearchResults.every(
        (result) => result.metadata?.numericId === 123,
      ),
    ).toBe(true);
  });

  test("Search with range filter should return documents within range", async () => {
    const response = await client.retrieval.search({
      query: "Test query",
      searchSettings: {
        filters: {
          "metadata.numericId": {
            $gte: 500,
          },
        },
      },
    });

    expect(response.results.chunkSearchResults).toBeDefined();
    expect(
      response.results.chunkSearchResults.every((result) => {
        const numericId = result.metadata?.numericId;
        return numericId >= 100 && numericId <= 500;
      }),
    ).toBe(true);
  });

  test("Search without filters should return both documents", async () => {
    const response = await client.retrieval.search({
      query: "Test query",
    });

    expect(response.results.chunkSearchResults).toBeDefined();
    expect(response.results.chunkSearchResults.length).toBeGreaterThan(0);

    const numericIds = response.results.chunkSearchResults.map((result) => {
      return result.metadata?.numericId || result.metadata?.numericid;
    });

    expect(numericIds.filter((id) => id !== undefined)).toContain(123);
    expect(numericIds.filter((id) => id !== undefined)).toContain(456);
  });

  // test("Filter on collection_id", async () => {
  //   const response = await client.retrieval.search({
  //     query: "Test query",
  //     searchSettings: {
  //       filters: {
  //         collection_ids: {
  //           $in: ["122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"],
  //         },
  //       },
  //     },
  //   });
  //   expect(response.results.chunkSearchResults).toBeDefined();
  //   expect(response.results.chunkSearchResults.length).toBeGreaterThan(0);
  //   expect(response.results.chunkSearchResults[0].collectionIds).toContain(
  //     "122fdf6a-e116-546b-a8f6-e4cb2e2c0a09",
  //   );
  // });

  test("Filter on non-existant column should return empty", async () => {
    const response = await expect(
      client.retrieval.search({
        query: "Test query",
        searchSettings: {
          filters: {
            nonExistentColumn: {
              $eq: ["122fdf6a-e116-546b-a8f6-e4cb2e2c0a09"],
            },
          },
        },
      }),
    );
  });

  test("Delete marmeladov.txt", async () => {
    const response = await client.documents.delete({
      id: "649d1072-7054-4e17-bd51-1af5f467d617",
    });

    expect(response.results).toBeDefined();
  });

  test("Delete untitled document", async () => {
    const response = await client.documents.delete({
      id: "5556836e-a51c-57c7-916a-de76c79df2b6",
    });

    expect(response.results).toBeDefined();
  });

  test("Delete document with URL", async () => {
    const response = await client.documents.delete({
      id: documentId2,
    });

    expect(response.results).toBeDefined();
  });

  test("Delete another document with URL", async () => {
    const response = await client.documents.delete({
      id: documentId3,
    });

    expect(response.results).toBeDefined();
  });

  test("Delete document with 'fast' ingestion mode", async () => {
    const response = await client.documents.delete({
      id: documentId4,
    });

    expect(response.results).toBeDefined();
  });

  test("Delete invalid JSON document", async () => {
    const response = await client.documents.delete({
      id: "04ebba11-8d7c-5e7e-ade8-8f02edee2327",
    });

    expect(response.results).toBeDefined();
  });
});
