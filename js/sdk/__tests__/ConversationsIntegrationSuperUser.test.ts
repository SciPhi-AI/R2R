import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect, afterAll } from "@jest/globals";
import fs from "fs";
import path from "path";

const baseUrl = "http://localhost:7272";
const TEST_OUTPUT_DIR = path.join(__dirname, "test-output");

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let conversationId: string;
  let messageId: string;

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

  test("List all conversations", async () => {
    const response = await client.conversations.list();
    expect(response.results).toBeDefined();
  });

  test("Create a conversation with a name", async () => {
    const response = await client.conversations.create({
      name: "Test Conversation",
    });
    conversationId = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.name).toBe("Test Conversation");
  });

  test("Update a conversation name", async () => {
    const response = await client.conversations.update({
      id: conversationId,
      name: "Updated Name",
    });
    expect(response.results).toBeDefined();
    expect(response.results.name).toBe("Updated Name");
  });

  test("Delete a conversation", async () => {
    const response = await client.conversations.delete({ id: conversationId });
    expect(response.results).toBeDefined();
  });

  test("Create a conversation", async () => {
    const response = await client.conversations.create();
    conversationId = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.name).toBeNull();
  });

  test("Add a message to a conversation", async () => {
    const response = await client.conversations.addMessage({
      id: conversationId,
      content: "Hello, world!",
      role: "user",
    });
    messageId = response.results.id;
    expect(response.results).toBeDefined();
  });

  test("Update message content only", async () => {
    const newContent = "Updated content";
    const response = await client.conversations.updateMessage({
      id: conversationId,
      messageID: messageId,
      content: newContent,
    });
    expect(response.results).toBeDefined();
    expect(response.results.message.content).toBe(newContent);
    expect(response.results.metadata.edited).toBe(true);
  });

  test("Update metadata only", async () => {
    const newMetadata = { test: "value" };
    const response = await client.conversations.updateMessage({
      id: conversationId,
      messageID: messageId,
      metadata: newMetadata,
    });
    expect(response.results).toBeDefined();
    expect(response.results.metadata.test).toBe("value");
    expect(response.results.metadata.edited).toBe(true);
    expect(response.results.message.content).toBe("Updated content");
  });

  test("Update both content and metadata", async () => {
    const newContent = "Both updated";
    const newMetadata = { key: "value" };
    const response = await client.conversations.updateMessage({
      id: conversationId,
      messageID: messageId,
      content: newContent,
      metadata: newMetadata,
    });
    expect(response.results).toBeDefined();
    expect(response.results.message.content).toBe(newContent);
    expect(response.results.metadata.key).toBe("value");
    expect(response.results.metadata.edited).toBe(true);
  });

  test("Handle empty message update", async () => {
    const response = await client.conversations.updateMessage({
      id: conversationId,
      messageID: messageId,
    });
    expect(response.results).toBeDefined();
    expect(response.results.message.content).toBe("Both updated");
    expect(response.results.metadata.edited).toBe(true);
  });

  test("Reject update with invalid conversation ID", async () => {
    await expect(
      client.conversations.updateMessage({
        id: "invalid-id",
        messageID: messageId,
        content: "test",
      }),
    ).rejects.toThrow();
  });

  test("Reject update with invalid message ID", async () => {
    await expect(
      client.conversations.updateMessage({
        id: conversationId,
        messageID: "invalid-message-id",
        content: "test",
      }),
    ).rejects.toThrow();
  });

  test("Export conversations to CSV with default options", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "conversations_default.csv");
    await client.conversations.export({ outputPath });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
    expect(content.split("\n").length).toBeGreaterThan(1);
  });

  test("Export conversations to CSV with custom columns", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "conversations_custom.csv");
    await client.conversations.export({
      outputPath,
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

  test("Export filtered conversations to CSV", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "conversations_filtered.csv");
    await client.conversations.export({
      outputPath: outputPath,
      filters: { document_type: { $eq: "txt" } },
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
  });

  test("Export conversations without headers", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "conversations_no_header.csv",
    );
    await client.conversations.export({
      outputPath: outputPath,
      includeHeader: false,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
  });

  test("Handle empty conversations export result", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "conversations_empty.csv");
    await client.conversations.export({
      outputPath: outputPath,
      filters: { name: { $eq: "non_existent_name" } },
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content.split("\n").filter((line) => line.trim()).length).toBe(1);
  });

  test("Export messages to CSV with default options", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "messages_default.csv");
    await client.conversations.exportMessages({ outputPath: outputPath });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
    expect(content.split("\n").length).toBeGreaterThan(1);
  });

  test("Export messages to CSV with custom columns", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "messages_custom.csv");
    await client.conversations.exportMessages({
      outputPath: outputPath,
      columns: ["id", "content", "created_at"],
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    const headers = content
      .split("\n")[0]
      .split(",")
      .map((h) => h.trim());

    expect(headers).toContain('"id"');
    expect(headers).toContain('"content"');
    expect(headers).toContain('"created_at"');
  });

  test("Export filtered messages to CSV", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "messages_filtered.csv");
    await client.conversations.exportMessages({
      outputPath: outputPath,
      filters: { conversation_id: { $eq: conversationId } },
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
  });

  test("Export messages without headers", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "messages_no_header.csv");
    await client.conversations.exportMessages({
      outputPath: outputPath,
      includeHeader: false,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
  });

  test("Handle empty messages export result", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "messages_empty.csv");
    await client.conversations.exportMessages({
      outputPath: outputPath,
      filters: { content: { $eq: '"non_existent_type"' } },
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content.split("\n").filter((line) => line.trim()).length).toBe(1);
  });

  test("Delete a conversation", async () => {
    const response = await client.conversations.delete({ id: conversationId });
    expect(response.results).toBeDefined();
  });
});
