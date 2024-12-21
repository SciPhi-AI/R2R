import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

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

  test("Delete a conversation", async () => {
    const response = await client.conversations.delete({ id: conversationId });
    expect(response.results).toBeDefined();
  });
});
