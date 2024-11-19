import { r2rClient } from "../src/index";
const fs = require("fs");
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
    const response = await client.users.register({
      email: "system_integration_test_user@example.com",
      password: "change_me_immediately",
    });

    userId = response.results.id;
    name = response.results.name;
    expect(response.results).toBeDefined();
    expect(response.results.is_superuser).toBe(false);
    expect(response.results.name).toBe(null);
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

  test("Only a superuser can call the `system/logs` endpoint.", async () => {
    await expect(client.system.logs({})).rejects.toThrow(/Status 403/);
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
