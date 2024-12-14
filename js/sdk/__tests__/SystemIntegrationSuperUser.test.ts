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

  test("Get the health of the system", async () => {
    const response = await client.system.health();
    expect(response.results).toBeDefined();
  });

  test("Get the settings of the system", async () => {
    const response = await client.system.settings();
    expect(response.results).toBeDefined();
  });

  test("Get the status of the system", async () => {
    const response = await client.system.status();
    expect(response.results).toBeDefined();
  });
});
