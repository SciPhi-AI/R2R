import { r2rClient } from "../src/index";
const fs = require("fs");
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

/**
 * raskolnikov.txt should have an id of `91662726-7271-51a5-a0ae-34818509e1fd`
 * karamozov.txt should have an id of `00f69fa0-c947-5f5f-a374-1837a1283366`
 * myshkin.txt should have an id of `0b80081e-a37a-579f-a06d-7d2032435d65`
 */

/**
 * Coverage
 *     - health
 *    Auth:
 *     - register
 *     X verifyEmail
 *     - login
 *     - logout
 *     - user
 *     - updateUser
 *     - refreshAccessToken
 *     - changePassword
 *     X requestPasswordReset
 *     X confirmPasswordReset
 *     - deleteUser
 *    Ingestion:
 *     - ingestFiles
 *     - updateFiles
 *     X ingestChunks
 *    Management:
 *     - serverStats
 *     X updatePrompt
 *     X analytics
 *     X logs
 *     - appSettings
 *     X scoreCompletion
 *     - usersOverview
 *     - delete
 *     X downloadFile
 *     - documentsOverview
 *     - documentChunks
 *     X inspectKnowledgeGraph
 *     X collectionsOverview
 *     X createCollection
 *     X getCollection
 *     X updateCollection
 *     X deleteCollection
 *     X listCollections
 *     X addUserToCollection
 *     X removeUserFromCollection
 *     X getUsersInCollection
 *     X getCollectionsForUser
 *     X assignDocumentToCollection
 *     X removeDocumentFromCollection
 *     X getDocumentCollections
 *     X getDocumentsInCollection
 *    Restructure:
 *     X enrichGraph
 *    Retrieval:
 *     - search
 *     X rag
 *     X streamingRag
 *     X agent
 *     X streamingAgent
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

  test("User", async () => {
    const asdf = await client.user();

    await expect(client.user()).resolves.not.toThrow();
  });

  test("Update user profile", async () => {
    const userId = "2bf8fd84-91ec-5048-9eb8-cf2ee9d66b64";
    const email = "newemail@example.com";
    const name = "New Name";
    const bio = "Updated bio";
    const profilePicture = "http://example.com/new-profile-pic.jpg";

    await expect(
      client.updateUser(userId, email, undefined, name, bio, profilePicture),
    ).resolves.not.toThrow();
  });

  test("Login", async () => {
    await expect(
      client.login("newemail@example.com", "password"),
    ).resolves.not.toThrow();
  });

  test("Ingest file", async () => {
    const files = [
      { path: "examples/data/raskolnikov.txt", name: "raskolnikov.txt" },
    ];

    await expect(
      client.ingestFiles(files, {
        metadatas: [{ title: "raskolnikov.txt" }],
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
      }),
    ).resolves.not.toThrow();
  });

  test("Search documents", async () => {
    await expect(client.search("test")).resolves.not.toThrow();
  });

  // Deletes rasolnikov.txt
  test("Delete document", async () => {
    await expect(
      client.delete({
        document_id: {
          $eq: "91662726-7271-51a5-a0ae-34818509e1fd",
        },
      }),
    ).resolves.not.toThrow();
  });

  test("Only an authorized user can call server stats", async () => {
    await expect(client.serverStats()).rejects.toThrow(
      "Status 403: Only an authorized user can call the `server_stats` endpoint.",
    );
  });

  test("Only a superuser can call app settings", async () => {
    await expect(client.appSettings()).rejects.toThrow(
      "Status 403: Only a superuser can call the `app_settings` endpoint.",
    );
  });

  test("Only a superuser can call users overview", async () => {
    await expect(client.usersOverview()).rejects.toThrow(
      "Status 403: Only a superuser can call the `users_overview` endpoint.",
    );
  });

  test("Document chunks", async () => {
    await expect(
      client.documentChunks("00f69fa0-c947-5f5f-a374-1837a1283366"),
    ).resolves.not.toThrow();
  });

  test("Refresh access token", async () => {
    await expect(client.refreshAccessToken()).resolves.not.toThrow();
  });

  test("Get documents overview", async () => {
    await expect(client.documentsOverview()).resolves.not.toThrow();
  });

  test("Logout", async () => {
    await expect(client.logout()).resolves.not.toThrow();
  });

  test("Login after logout", async () => {
    await expect(
      client.login("newemail@example.com", "password"),
    ).resolves.not.toThrow();
  });

  test("Clean up remaining documents", async () => {
    // Deletes karamozov.txt
    await expect(
      client.delete({
        document_id: {
          $eq: "00f69fa0-c947-5f5f-a374-1837a1283366",
        },
      }),
    ).resolves.not.toThrow();

    // Deletes myshkin.txt
    await expect(
      client.delete({
        document_id: {
          $eq: "0b80081e-a37a-579f-a06d-7d2032435d65",
        },
      }),
    ).resolves.not.toThrow;
  });

  test("Change password", async () => {
    await expect(
      client.changePassword("password", "new_password"),
    ).resolves.not.toThrow();
  });

  test("Delete User", async () => {
    const currentUser = await client.user();
    await expect(
      client.deleteUser(currentUser.results.id, "new_password"),
    ).resolves.not.toThrow();
  });
});
