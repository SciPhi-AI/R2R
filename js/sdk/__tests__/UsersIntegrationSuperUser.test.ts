import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Users Integration Tests", () => {
  let client: r2rClient;
  let userId: string;
  let name: string | undefined;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
  });

  test("Register a new user", async () => {
    const response = await client.users.register({
      email: "new_user@example.com",
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
      email: "new_user@example.com",
      password: "change_me_immediately",
    });
    expect(response.results).toBeDefined();
  });

  test("Logout as a user", async () => {
    await client.users.logout();
  });

  test("Login as a user after logout", async () => {
    const response = await client.users.login({
      email: "new_user@example.com",
      password: "change_me_immediately",
    });
    expect(response.results).toBeDefined();
  });

  test("Change a user's password", async () => {
    const response = await client.users.changePassword({
      current_password: "change_me_immediately",
      new_password: "i_was_changed_immediately",
    });
    expect(response.results).toBeDefined();
  });

  test("Logout and login with new password", async () => {
    await client.users.logout();

    const login_response = await client.users.login({
      email: "new_user@example.com",
      password: "i_was_changed_immediately",
    });
    expect(login_response.results).toBeDefined();
  });

  test("Retrieve the current user", async () => {
    const response = await client.users.me();
    expect(response.results).toBeDefined();
  });

  test("Retrieve a user", async () => {
    const response = await client.users.retrieve({ id: userId });
    expect(response.results).toBeDefined();
  });

  test("Update a user", async () => {
    const response = await client.users.update({
      id: userId,
      name: "New Name",
    });
    expect(response.results).toBeDefined();
  });

  test("Retrieve a user after update", async () => {
    const response = await client.users.retrieve({ id: userId });
    expect(response.results).toBeDefined();
  });

  test("List user's collections", async () => {
    const response = await client.users.listCollections({ id: userId });
    expect(response.results).toBeDefined();
    expect(Array.isArray(response.results)).toBe(true);
  });

  test("Delete a user", async () => {
    const response = await client.users.delete({
      id: userId,
      password: "i_was_changed_immediately",
    });
    expect(response.results).toBeDefined();
  });
});
