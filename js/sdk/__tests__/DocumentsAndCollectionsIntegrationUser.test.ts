import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 System Integration Tests User", () => {
  let client: r2rClient;
  let user1Client: r2rClient;
  let user2Client: r2rClient;
  let user1Id: string;
  let user2Id: string;
  let user1Name: string | undefined;
  let user2Name: string | undefined;

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
    const response = await client.users.register({
      email: "user_1@example.com",
      password: "change_me_immediately",
    });

    user1Id = response.results.id;
    user1Name = response.results.name;
    expect(response.results).toBeDefined();
    expect(response.results.is_superuser).toBe(false);
    expect(response.results.name).toBe(null);
  });

  test("Login as a user 1", async () => {
    const response = await user1Client.users.login({
      email: "user_1@example.com",
      password: "change_me_immediately",
    });
    expect(response.results).toBeDefined();
  });

  test("Register user 2", async () => {
    const response = await client.users.register({
      email: "user_2@example.com",
      password: "change_me_immediately",
    });

    user2Id = response.results.id;
    user2Name = response.results.name;
    expect(response.results).toBeDefined();
    expect(response.results.is_superuser).toBe(false);
    expect(response.results.name).toBe(null);
  });

  test("Login as a user 2", async () => {
    const response = await user2Client.users.login({
      email: "user_2@example.com",
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
