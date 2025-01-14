import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.users.login({
      email: "admin@example.com",
      password: "change_me_immediately",
    });
  });

  test("List prompts", async () => {
    const response = await client.prompts.list();
    expect(response.results).toBeDefined();
  });

  test("Create a prompt", async () => {
    const response = await client.prompts.create({
      name: "test-prompt",
      template: "Hello, {name}!",
      inputTypes: { name: "string" },
    });
    expect(response.results).toBeDefined();
  });

  test("Retrieve a prompt", async () => {
    const response = await client.prompts.retrieve({
      name: "test-prompt",
    });
    expect(response.results).toBeDefined();
  });

  test("Update a prompt", async () => {
    const response = await client.prompts.update({
      name: "test-prompt",
      template: "Hello, {name}! How are you?",
      inputTypes: { name: "string" },
    });
    expect(response.results).toBeDefined();
  });

  test("Delete a prompt", async () => {
    const response = await client.prompts.delete({
      name: "test-prompt",
    });
    expect(response.results).toBeDefined();
  });
});
