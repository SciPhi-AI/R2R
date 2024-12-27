import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let user1Client: r2rClient;
  let user2Client: r2rClient;
  let user1Id: string;
  let user2Id: string;
  let conversationId: string;
  let user1ConversationId: string;
  let user2ConversationId: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    user1Client = new r2rClient(baseUrl);
    user2Client = new r2rClient(baseUrl);

    await client.users.login({
      email: "admin@example.com",
      password: "change_me_immediately",
    });
  });

  test("Register user 1", async () => {
    const response = await client.users.create({
      email: "user1@example.com",
      password: "change_me_immediately",
    });

    user1Id = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.isSuperuser).toBe(false);
    expect(response.results.name).toBe(null);
  });

  test("Login as a user 1", async () => {
    const response = await user1Client.users.login({
      email: "user1@example.com",
      password: "change_me_immediately",
    });
    expect(response.results).toBeDefined();
  });

  test("Register user 2", async () => {
    const response = await client.users.create({
      email: "user2@example.com",
      password: "change_me_immediately",
    });

    user2Id = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.isSuperuser).toBe(false);
    expect(response.results.name).toBe(null);
  });

  test("Login as a user 2", async () => {
    const response = await user2Client.users.login({
      email: "user2@example.com",
      password: "change_me_immediately",
    });
    expect(response.results).toBeDefined();
  });

  test("Get the health of the system", async () => {
    const response = await client.system.health();
    expect(response.results).toBeDefined();
  });

  test("Get the health of the system as user 1", async () => {
    const response = await user1Client.system.health();
    expect(response.results).toBeDefined();
  });

  test("Get the health of the system as user 2", async () => {
    const response = await user2Client.system.health();
    expect(response.results).toBeDefined();
  });

  test("List all conversations", async () => {
    const response = await client.conversations.list();

    expect(response.results).toBeDefined();
    expect(response.results).toEqual([]);
    expect(response.totalEntries).toBe(0);
  });

  test("List all conversations as user 1", async () => {
    const response = await user1Client.conversations.list();

    expect(response.results).toBeDefined();
    expect(response.results).toEqual([]);
    expect(response.totalEntries).toBe(0);
  });

  test("List all conversations as user 2", async () => {
    const response = await user2Client.conversations.list();

    expect(response.results).toBeDefined();
    expect(response.results).toEqual([]);
    expect(response.totalEntries).toBe(0);
  });

  test("Create a conversation with a name", async () => {
    const response = await client.conversations.create({
      name: "Test Conversation",
    });
    conversationId = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.name).toBe("Test Conversation");
  });

  test("Create a conversation with a name as user 1", async () => {
    const response = await user1Client.conversations.create({
      name: "User 1 Conversation",
    });
    user1ConversationId = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.name).toBe("User 1 Conversation");
  });

  test("Create a conversation with a name as user 2", async () => {
    const response = await user2Client.conversations.create({
      name: "User 2 Conversation",
    });
    user2ConversationId = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.name).toBe("User 2 Conversation");
  });

  test("Update a conversation name", async () => {
    const response = await client.conversations.update({
      id: conversationId,
      name: "Updated Name",
    });
    expect(response.results).toBeDefined();
    expect(response.results.name).toBe("Updated Name");
  });

  test("Update a conversation name as user 1", async () => {
    const response = await user1Client.conversations.update({
      id: user1ConversationId,
      name: "User 1 Updated Name",
    });
    expect(response.results).toBeDefined();
    expect(response.results.name).toBe("User 1 Updated Name");
  });

  test("Update a conversation name as user 2", async () => {
    const response = await user2Client.conversations.update({
      id: user2ConversationId,
      name: "User 2 Updated Name",
    });
    expect(response.results).toBeDefined();
    expect(response.results.name).toBe("User 2 Updated Name");
  });

  test("Add a message to a conversation", async () => {
    const response = await client.conversations.addMessage({
      id: conversationId,
      content: "Hello, world!",
      role: "user",
    });
    expect(response.results).toBeDefined();
  });

  test("Add a message to a conversation as user 1", async () => {
    const response = await user1Client.conversations.addMessage({
      id: user1ConversationId,
      content: "Hello, world!",
      role: "user",
    });
    expect(response.results).toBeDefined();
  });

  test("Add a message to a conversation as user 2", async () => {
    const response = await user2Client.conversations.addMessage({
      id: user2ConversationId,
      content: "Hello, world!",
      role: "user",
    });
    expect(response.results).toBeDefined();
  });

  test("User 1 should not be able to see user 2's conversation", async () => {
    await expect(
      user1Client.conversations.retrieve({ id: user2ConversationId }),
    ).rejects.toThrow(/Status 404/);
  });

  test("User 2 should not be able to see user 1's conversation", async () => {
    await expect(
      user2Client.conversations.retrieve({ id: user1ConversationId }),
    ).rejects.toThrow(/Status 404/);
  });

  test("User 1 should not see user 2's conversation when listing all conversations", async () => {
    const response = await user1Client.conversations.list();
    expect(response.results).toHaveLength(1);
  });

  test("User 2 should not see user 1's conversation when listing all conversations", async () => {
    const response = await user2Client.conversations.list();
    expect(response.results).toHaveLength(1);
  });

  test("The super user should see all conversations when listing all conversations", async () => {
    const response = await client.conversations.list();
    expect(response.results).toHaveLength(3);
  });

  test("Delete a conversation", async () => {
    const response = await client.conversations.delete({ id: conversationId });
    expect(response.results).toBeDefined();
  });

  test("User 1 should not be able to delete user 2's conversation", async () => {
    await expect(
      user1Client.conversations.delete({ id: user2ConversationId }),
    ).rejects.toThrow(/Status 404/);
  });

  test("User 2 should not be able to delete user 1's conversation", async () => {
    await expect(
      user2Client.conversations.delete({ id: user1ConversationId }),
    ).rejects.toThrow(/Status 404/);
  });

  test("Delete a conversation as user 1", async () => {
    const response = await user1Client.conversations.delete({
      id: user1ConversationId,
    });
    expect(response.results).toBeDefined();
  });

  test("Super user should be able to delete any conversation", async () => {
    const response = await client.conversations.delete({
      id: user2ConversationId,
    });
    expect(response.results).toBeDefined();
  });

  test("Delete user 1", async () => {
    const response = await client.users.delete({
      id: user1Id,
      password: "change_me_immediately",
    });
    expect(response.results).toBeDefined();
  });

  test("Delete user 2", async () => {
    const response = await client.users.delete({
      id: user2Id,
      password: "change_me_immediately",
    });
    expect(response.results).toBeDefined();
  });
});
