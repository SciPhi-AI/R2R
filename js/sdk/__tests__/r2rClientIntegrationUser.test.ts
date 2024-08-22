import { r2rClient } from "../src/index";
const fs = require("fs");

const baseUrl = "http://localhost:8000";

/**
 * raskolnikov.txt should have an id of `91662726-7271-51a5-a0ae-34818509e1fd`
 * karamozov.txt should have an id of `00f69fa0-c947-5f5f-a374-1837a1283366`
 * myshkin.txt should have an id of `0b80081e-a37a-579f-a06d-7d2032435d65`
 */

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
        metadatas: [{ title: "raskolnikov.txt" }],
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
        document_ids: ["0b80081e-a37a-579f-a06d-7d2032435d65"],
        metadatas: [{ title: "updated_karamozov.txt" }],
      }),
    ).resolves.not.toThrow();
  });

  test("Search documents", async () => {
    await expect(client.search("test")).resolves.not.toThrow();
  });

  // Deletes rasolnikov.txt
  test("Delete document", async () => {
    await expect(
      client.delete({ document_id: "91662726-7271-51a5-a0ae-34818509e1fd" }),
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
    // Deletes karamozov.txt
    await expect(
      client.delete({ document_id: "00f69fa0-c947-5f5f-a374-1837a1283366" }),
    ).resolves.not.toThrow();

    // Deletes myshkin.txt
    await expect(
      client.delete({ document_id: "0b80081e-a37a-579f-a06d-7d2032435d65" }),
    ).resolves.not.toThrow;
  });

  test("Change password", async () => {
    await expect(
      client.changePassword("password", "new_password"),
    ).resolves.not.toThrow();
  });

  // TODO: Fix this test
  // test("Delete User", async () => {
  //   const currentUser = await client.user();
  //   await expect(client.deleteUser(currentUser.id, "new_password")).resolves.not.toThrow();
  // });
});
