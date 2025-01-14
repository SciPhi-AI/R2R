import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 System Integration Tests User", () => {
  let client: r2rClient;
  let userId: string;
  let name: string | undefined;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
  });

  test("Register a new user", async () => {
    const response = await client.users.create({
      email: "system_integration_test_user@example.com",
      password: "change_me_immediately",
      name: "Test User",
      bio: "This is the bio of the test user.",
    });

    userId = response.results.id;
    name = response.results.name;
    expect(response.results).toBeDefined();
    expect(response.results.isSuperuser).toBe(false);
    expect(response.results.name).toBe("Test User");
    expect(response.results.bio).toBe("This is the bio of the test user.");
  });

  test("Login as a user", async () => {
    const response = await client.users.login({
      email: "system_integration_test_user@example.com",
      password: "change_me_immediately",
    });
    expect(response.results).toBeDefined();
  });

  test("Get the health of the system", async () => {
    const response = await client.system.health();
    expect(response.results).toBeDefined();
  });

  test("Only a superuser can call the `system/settings` endpoint.", async () => {
    await expect(client.system.settings()).rejects.toThrow(/Status 403/);
  });

  test("Only an authorized user can call the `system/status` endpoint.", async () => {
    await expect(client.system.status()).rejects.toThrow(/Status 403/);
  });

  test("Delete a user", async () => {
    const response = await client.users.delete({
      id: userId,
      password: "change_me_immediately",
    });
    expect(response.results).toBeDefined();
  });
});
