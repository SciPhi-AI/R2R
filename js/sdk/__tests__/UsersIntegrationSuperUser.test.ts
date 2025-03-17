import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect, afterAll } from "@jest/globals";
import fs from "fs";
import path from "path";

const baseUrl = "http://localhost:7272";
const TEST_OUTPUT_DIR = path.join(__dirname, "test-output");

describe("r2rClient V3 Users Integration Tests", () => {
  let client: r2rClient;
  let superUserClient: r2rClient;
  let userId: string;
  let name: string | undefined;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    superUserClient = new r2rClient(baseUrl);

    await superUserClient.users.login({
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

  test("Register a new user", async () => {
    const response = await client.users.create({
      email: "new_user@example.com",
      password: "change_me_immediately",
    });

    userId = response.results.id;
    name = response.results.name;

    expect(response.results).toBeDefined();
    expect(response.results.id).toBeDefined();
    expect(response.results.email).toBe("new_user@example.com");
    expect(response.results.isActive).toBeDefined();
    expect(response.results.isSuperuser).toBe(false);
    expect(response.results.createdAt).toBeDefined();
    expect(response.results.updatedAt).toBeDefined();
    // expect(response.results.is_verified).toBe(false);
    expect(response.results.collectionIds).toBeDefined();
    // expect(response.results.hashed_password).toBeUndefined();
    // expect(response.results.verification_code_expiry).toBeUndefined();
    expect(response.results.name).toBe(null);
    expect(response.results.bio).toBe(null);
    expect(response.results.profilePicture).toBe(null);
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

  test("Request verification email", async () => {
    await expect(
      client.users.sendVerificationEmail({
        email: "new_user@example.com",
      }),
    ).rejects.toThrow(/Status 400/);
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
      bio: "New Bio",
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBeDefined();
    expect(response.results.email).toBe("new_user@example.com");
    expect(response.results.isActive).toBeDefined();
    expect(response.results.isSuperuser).toBe(false);
    expect(response.results.createdAt).toBeDefined();
    expect(response.results.updatedAt).toBeDefined();
    // expect(response.results.is_verified).toBe(false);
    expect(response.results.collectionIds).toBeDefined();
    // expect(response.results.hashed_password).toBeUndefined();
    // expect(response.results.verification_code_expiry).toBeUndefined();
    expect(response.results.name).toBe("New Name");
    expect(response.results.bio).toBe("New Bio");
    expect(response.results.profilePicture).toBe(null);
  });

  test("Retrieve a user after update", async () => {
    const response = await client.users.retrieve({ id: userId });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBeDefined();
    expect(response.results.email).toBe("new_user@example.com");
    expect(response.results.isActive).toBeDefined();
    expect(response.results.isSuperuser).toBe(false);
    expect(response.results.createdAt).toBeDefined();
    expect(response.results.updatedAt).toBeDefined();
    // expect(response.results.is_verified).toBe(false);
    expect(response.results.collectionIds).toBeDefined();
    // expect(response.results.hashed_password).toBeUndefined();
    // expect(response.results.verification_code_expiry).toBeUndefined();
    expect(response.results.name).toBe("New Name");
    expect(response.results.bio).toBe("New Bio");
    expect(response.results.profilePicture).toBe(null);
  });

  test("List user's collections", async () => {
    const response = await client.users.listCollections({ id: userId });
    expect(response.results).toBeDefined();
    expect(Array.isArray(response.results)).toBe(true);
  });

  test("List users as superuser and filter with user ID", async () => {
    const response = await superUserClient.users.list({
      ids: [userId],
    });

    expect(response.results).toBeDefined();
    expect(Array.isArray(response.results)).toBe(true);
    expect(response.results.length).toBe(1);
    expect(response.results[0].id).toBe(userId);
  });

  test("Mark new user as superuser", async () => {
    const response = await superUserClient.users.update({
      id: userId,
      isSuperuser: true,
    });

    expect(response.results).toBeDefined();
    expect(response.results.isSuperuser).toBe(true);
  });

  test("Retrieve the updated user", async () => {
    const response = await client.users.retrieve({ id: userId });
    expect(response.results).toBeDefined();
    expect(response.results.isSuperuser).toBe(true);
  });

  test("Make the user a normal user again", async () => {
    const response = await superUserClient.users.update({
      id: userId,
      isSuperuser: false,
    });

    expect(response.results).toBeDefined();
    expect(response.results.isSuperuser).toBe(false);
  });

  test("Delete a user", async () => {
    const response = await client.users.delete({
      id: userId,
      password: "i_was_changed_immediately",
    });
    expect(response.results).toBeDefined();
  });

  test("Export users to CSV with default options", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "users_default.csv");
    await superUserClient.users.export({ outputPath });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
    expect(content.split("\n").length).toBeGreaterThan(1);
  });

  test("Export users to CSV with custom columns", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "users_custom.csv");
    await superUserClient.users.export({
      outputPath,
      columns: ["id", "is_superuser", "created_at"],
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    const headers = content
      .split("\n")[0]
      .split(",")
      .map((h) => h.trim());

    expect(headers).toContain('"id"');
    expect(headers).toContain('"is_superuser"');
    expect(headers).toContain('"created_at"');
  });

  test("Export filtered users to CSV", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "users_filtered.csv");
    await superUserClient.users.export({
      outputPath,
      filters: { is_superuser: { $eq: true } },
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
  });

  test("Export users without headers", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "users_no_header.csv");
    await superUserClient.users.export({
      outputPath,
      includeHeader: false,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
  });

  test("Handle empty export result", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "users_empty.csv");
    await superUserClient.users.export({
      outputPath,
      filters: { is_superuser: { $eq: false } },
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content.split("\n").filter((line) => line.trim()).length).toBe(1);
  });
});
