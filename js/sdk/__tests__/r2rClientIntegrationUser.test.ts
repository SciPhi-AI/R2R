import { r2rClient } from "../src/index";
const fs = require("fs");

const baseUrl = "http://localhost:8000";

describe("r2rClient Integration Tests", () => {
  let client: r2rClient;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
  });

  test("Health check", async () => {
    await expect(client.health()).resolves.not.toThrow();
  });

  test("Register user", async () => {
    await expect(
      client.register("test@gmail.com", "password"),
    ).resolves.not.toThrow();
  });

  test("Verify Email throws a 400 error", async () => {
    await expect(client.verifyEmail("verification_code")).rejects.toThrow(
      "Status 400: Email verification is not required",
    );
  });

  test("Login", async () => {
    await expect(
      client.login("test@gmail.com", "password"),
    ).resolves.not.toThrow();
  });

  test("Ingest file", async () => {
    const files = [
      { path: "examples/data/raskolnikov.txt", name: "raskolnikov.txt" },
    ];

    await expect(
      client.ingestFiles(files, {
        metadatas: [{ title: "myshkin.txt" }, { title: "karamozov.txt" }],
        skip_document_info: false,
      }),
    ).resolves.not.toThrow();
  });

  test("Ingest files in folder", async () => {
    const files = ["examples/data/folder"];

    await expect(client.ingestFiles(files)).resolves.not.toThrow();
  });

  test("Update files", async () => {
    const updated_file = [
      { path: "examples/data/folder/myshkin.txt", name: "myshkin.txt" },
    ];
    await expect(
      client.updateFiles(updated_file, {
        document_ids: ["06f6aab5-daa1-5b22-809c-d73a378600ed"],
        metadatas: [{ title: "updated_karamozov.txt" }],
      }),
    ).resolves.not.toThrow();
  });

  test("Search documents", async () => {
    await expect(client.search("test")).resolves.not.toThrow();
  });

  test("Generate RAG response", async () => {
    await expect(client.rag("test")).resolves.not.toThrow();
  }, 30000);

  test("Delete document", async () => {
    await expect(
      client.delete({ document_id: "c621c119-e21d-5d11-a099-bab1993f76d0" }),
    ).resolves.not.toThrow();
  });

  test("Only a superuser can call app settings", async () => {
    await expect(client.appSettings()).rejects.toThrow(
      "Status 403: Only a superuser can call the `app_settings` endpoint.",
    );
  });

  test("Get documents overview", async () => {
    await expect(client.documentsOverview()).resolves.not.toThrow();
  });

  test("Logout", async () => {
    await expect(client.logout()).resolves.not.toThrow();
  });

  test("Login after logout", async () => {
    await expect(
      client.login("test@gmail.com", "password"),
    ).resolves.not.toThrow();
  });

  test("Clean up remaining documents", async () => {
    await expect(
      client.delete({ document_id: "f58d4ec4-0274-56fa-b1ce-16aa3ba9ce3c" }),
    ).resolves.not.toThrow();

    await expect(
      client.delete({ document_id: "06f6aab5-daa1-5b22-809c-d73a378600ed" }),
    ).resolves.not.toThrow;
  });

  test("Change password", async () => {
    await expect(
      client.changePassword("password", "new_password"),
    ).resolves.not.toThrow();
  });

  test("Delete User", async () => {
    await expect(client.deleteUser("new_password")).resolves.not.toThrow();
  });
});
