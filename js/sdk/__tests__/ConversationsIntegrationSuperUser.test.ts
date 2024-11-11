import { r2rClient } from "../src/index";
const fs = require("fs");
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

  test("Create a conversation", async () => {
    const response = await client.conversations.create();
    conversationId = response.results.id;
    expect(response.results).toBeDefined();
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

  // TODO: This is throwing a 405? Why?
  // test("Update a message in a conversation", async () => {
  //   const response = await client.conversations.updateMessage({
  //     id: conversationId,
  //     message_id: messageId,
  //     content: "Hello, world! How are you?",
  //   });
  //   expect(response.results).toBeDefined();
  // });

  test("List branches in a conversation", async () => {
    const response = await client.conversations.listBranches({
      id: conversationId,
    });
    console.log("List branches response: ", response);
    expect(response.results).toBeDefined();
  });

  test("Delete a conversation", async () => {
    const response = await client.conversations.delete({ id: conversationId });
    expect(response.results).toBeDefined();
  });
});
