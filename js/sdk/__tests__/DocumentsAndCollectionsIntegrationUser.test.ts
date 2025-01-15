import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

/**
 * User 1's document will have an id of `70b39c87-a9a6-50ae-9bd0-b9460325ad81`
 * User 2's document will have an id of `43fd46da-b856-52c1-9ea7-2c4aaf84108c`
 * User 1's collection will have an id of `81c948ae-d41d-5d49-becf-d605444af636`
 * User 2's collection will have an id of `1f99a459-6d2e-5690-ad21-db026f019683`
 */
describe("r2rClient V3 System Integration Tests User", () => {
  let client: r2rClient;
  let user1Client: r2rClient;
  let user2Client: r2rClient;
  let user1Id: string;
  let user2Id: string;
  let user1DocumentId: string;
  let user2DocumentId: string;
  let user1Document2Id: string;
  let user2Document2Id: string;
  let user1CollectionId: string;
  let user2CollectionId: string;

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
    const response = await client.users.create({
      email: "user_1@example.com",
      password: "change_me_immediately",
    });

    user1Id = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.isSuperuser).toBe(false);
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
    const response = await client.users.create({
      email: "user_2@example.com",
      password: "change_me_immediately",
    });

    user2Id = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.isSuperuser).toBe(false);
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

  test("Get the collections of user 1", async () => {
    const response = await user1Client.collections.list();

    expect(response.results).toBeDefined();
    expect(response.results.length).toBe(1);
    expect(response.totalEntries).toBe(1);
    user1CollectionId = response.results[0].id;
  });

  test("Get the collections of user 2", async () => {
    const response = await user2Client.collections.list();

    expect(response.results).toBeDefined();
    expect(response.results.length).toBe(1);
    expect(response.totalEntries).toBe(1);
    user2CollectionId = response.results[0].id;
  });

  test("Create document as user 1 with file path", async () => {
    const response = await user1Client.documents.create({
      file: { path: "examples/data/marmeladov.txt", name: "marmeladov.txt" },
      metadata: { title: "marmeladov.txt" },
    });

    await new Promise((resolve) => setTimeout(resolve, 5000));

    expect(response.results.documentId).toBeDefined();
    user1DocumentId = response.results.documentId;
  }, 15000);

  test("Create document as user 2 with file path", async () => {
    const response = await user2Client.documents.create({
      file: { path: "examples/data/marmeladov.txt", name: "marmeladov.txt" },
      metadata: { title: "marmeladov.txt" },
    });

    await new Promise((resolve) => setTimeout(resolve, 5000));

    expect(response.results.documentId).toBeDefined();
    user2DocumentId = response.results.documentId;
  }, 15000);

  test("Retrieve document as user 1", async () => {
    const response = await user1Client.documents.retrieve({
      id: user1DocumentId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(user1DocumentId);
  });

  test("Retrieve document as user 2", async () => {
    const response = await user2Client.documents.retrieve({
      id: user2DocumentId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(user2DocumentId);
  });

  test("Create document as user 1 from raw text", async () => {
    const response = await user1Client.documents.create({
      raw_text: "Hello, world!",
      metadata: { title: "hello.txt" },
    });

    await new Promise((resolve) => setTimeout(resolve, 5000));

    expect(response.results.documentId).toBeDefined();
    user1Document2Id = response.results.documentId;
  }, 15000);

  test("Create document as user 2 from raw text", async () => {
    const response = await user2Client.documents.create({
      raw_text: "Hello, world!",
      metadata: { title: "hello.txt" },
    });

    await new Promise((resolve) => setTimeout(resolve, 5000));

    expect(response.results.documentId).toBeDefined();
    user2Document2Id = response.results.documentId;
  }, 15000);

  test("List documents with no parameters as user 1", async () => {
    const response = await user1Client.documents.list();

    expect(response.results).toBeDefined();
    expect(Array.isArray(response.results)).toBe(true);
  });

  test("List documents with no parameters as user 2", async () => {
    const response = await user2Client.documents.list();

    expect(response.results).toBeDefined();
    expect(Array.isArray(response.results)).toBe(true);
  });

  test("List document chunks as user 1", async () => {
    const response = await user1Client.documents.listChunks({
      id: user1DocumentId,
    });

    expect(response.results).toBeDefined();
    expect(Array.isArray(response.results)).toBe(true);
  });

  test("List document chunks as user 2", async () => {
    const response = await user2Client.documents.listChunks({
      id: user2DocumentId,
    });

    expect(response.results).toBeDefined();
    expect(Array.isArray(response.results)).toBe(true);
  });

  test("User 2 should not be able to list user 1's document chunks", async () => {
    await expect(
      user2Client.documents.listChunks({ id: user1DocumentId }),
    ).rejects.toThrow(/Status 403/);
  });

  test("User 1 should not be able to list user 2's document chunks", async () => {
    await expect(
      user1Client.documents.listChunks({ id: user2DocumentId }),
    ).rejects.toThrow(/Status 403/);
  });

  test("User 1 should not be able to delete user 2's document", async () => {
    await expect(
      user1Client.documents.delete({ id: user2Document2Id }),
    ).rejects.toThrow(/Status 404/);
  });

  test("User 2 should not be able to delete user 1's document", async () => {
    await expect(
      user2Client.documents.delete({ id: user1Document2Id }),
    ).rejects.toThrow(/Status 404/);
  });

  test("A superuser should be able to delete any document", async () => {
    const response = await client.documents.delete({ id: user1Document2Id });
    expect(response.results).toBeDefined();

    const response2 = await client.documents.delete({ id: user2Document2Id });
    expect(response2.results).toBeDefined();
  });

  // test("User 1's collection should have 2 documents", async () => {
  //   const response = await user1Client.collections.retrieve({
  //     id: user1CollectionId,
  //   });

  //   console.log(response);

  //   expect(response.results).toBeDefined();
  //   expect(response.results.documentCount).toBe(2);
  // });

  // test("User 2's collection should have 2 documents", async () => {
  //   const response = await user2Client.collections.retrieve({
  //     id: user2CollectionId,
  //   });

  //   console.log(response);

  //   expect(response.results).toBeDefined();
  //   expect(response.results.documentCount).toBe(1);
  // });

  test("Delete document as user 1", async () => {
    const response = await user1Client.documents.delete({
      id: user1DocumentId,
    });
    expect(response.results).toBeDefined();
  });

  test("Delete document as user 2", async () => {
    const response = await user2Client.documents.delete({
      id: user2DocumentId,
    });
    expect(response.results).toBeDefined();
  });

  // test("User 1's collection should have 0 documents after deletion", async () => {
  //   const response = await user1Client.collections.retrieve({
  //     id: user1CollectionId,
  //   });

  //   console.log(response);

  //   expect(response.results).toBeDefined();
  //   expect(response.results.documentCount).toBe(0);
  // });

  // test("User 2's collection should have 0 documents after deletion", async () => {
  //   const response = await user2Client.collections.retrieve({
  //     id: user2CollectionId,
  //   });

  //   console.log(response);

  //   expect(response.results).toBeDefined();
  //   expect(response.results.documentCount).toBe(0);
  // });

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
