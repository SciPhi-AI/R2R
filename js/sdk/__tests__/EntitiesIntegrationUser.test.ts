import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 System Integration Tests User", () => {
  let client: r2rClient;
  let user1Client: r2rClient;
  let user2Client: r2rClient;

  let user1Id: string;
  let user2Id: string;

  let user1Entity1Id: string;
  let user1Entity2Id: string;
  let user2Entity1Id: string;
  let user2Entity2Id: string;

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

  test("Create an entity as user 1", async () => {
    const response = await user1Client.entities.create({
      name: "Entity 1",
      description: "The first entity",
    });
    expect(response.results).toBeDefined();
    user1Entity1Id = response.results.id;
    expect(user1Entity1Id).toEqual(response.results.id);
    expect(response.results.name).toEqual("Entity 1");
    expect(response.results.description).toBe("The first entity");
  });

  test("Create another entity as user 1", async () => {
    const response = await user1Client.entities.create({
      name: "Entity 2",
      description: "The second entity",
    });
    expect(response.results).toBeDefined();
    user1Entity2Id = response.results.id;
    expect(user1Entity2Id).toEqual(response.results.id);
    expect(response.results.name).toEqual("Entity 2");
    expect(response.results.description).toBe("The second entity");
  });

  test("Create an entity as user 2", async () => {
    const response = await user2Client.entities.create({
      name: "Entity 1",
      description: "The first entity",
    });
    expect(response.results).toBeDefined();
    user2Entity1Id = response.results.id;
    expect(user2Entity1Id).toEqual(response.results.id);
    expect(response.results.name).toEqual("Entity 1");
    expect(response.results.description).toBe("The first entity");
  });

  test("Create another entity as user 2", async () => {
    const response = await user2Client.entities.create({
      name: "Entity 2",
      description: "The second entity",
    });
    expect(response.results).toBeDefined();
    user2Entity2Id = response.results.id;
    expect(user2Entity2Id).toEqual(response.results.id);
    expect(response.results.name).toEqual("Entity 2");
    expect(response.results.description).toBe("The second entity");
  });

  test("Ensure that there are four entities visable to the super user", async () => {
    const response = await client.entities.list();
    expect(response.results).toBeDefined();
    expect(response.results.length).toEqual(4);
  });

  test("Ensure that there are two entities visable to user 1", async () => {
    const response = await user1Client.entities.list();
    expect(response.results).toBeDefined();
    expect(response.results.length).toEqual(2);
  });

  test("Ensure that there are two entities visable to user 2", async () => {
    const response = await user2Client.entities.list();
    expect(response.results).toBeDefined();
    expect(response.results.length).toEqual(2);
  });

  test("User 1 should be able to retrieve their entities", async () => {
    const response = await user1Client.entities.retrieve({
      id: user1Entity1Id,
    });
    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(user1Entity1Id);
  });

//   test("User 1 should not be able to retrieve user 2's entities", async () => {
//     expect(
//       await user1Client.entities.retrieve({ id: user2Entity1Id }),
//     ).toThrowError();
//   });

  test("User 2 should be able to retrieve their entities", async () => {
    const response = await user2Client.entities.retrieve({
      id: user2Entity1Id,
    });
    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(user2Entity1Id);
  });

//   test("User 2 should not be able to retrieve user 1's entities", async () => {
//     expect(
//       await user2Client.entities.retrieve({ id: user1Entity1Id }),
//     ).toThrowError();
//   });

  test("A super user should be able to retrieve user 1's entities", async () => {
    const response = await client.entities.retrieve({ id: user1Entity1Id });
    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(user1Entity1Id);
  });

  test("A super user should be able to retrieve user 2's entities", async () => {
    const response = await client.entities.retrieve({ id: user2Entity1Id });
    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(user2Entity1Id);
  });

  //   test("User 1 should not be able to delete user 2's entities", async () => {
  //     const response = await user1Client.entities.delete({ id: user2Entity1Id });
  //     expect(response.results).toBeDefined();
  //     expect(response.results.success).toBe(false);
  //   });

  //   test("User 2 should not be able to delete user 1's entities", async () => {
  //     const response = await user2Client.entities.delete({ id: user1Entity1Id });
  //     expect(response.results).toBeDefined();
  //     expect(response.results.success).toBe(false);
  //   });

  //   test("Delete user 1's entities", async () => {
  //     const firstResponse = await user1Client.entities.delete({
  //       id: user1Entity1Id,
  //     });
  //     expect(firstResponse.results).toBeDefined();
  //     expect(firstResponse.results.success).toBe(true);

  //     const secondResponse = await user1Client.entities.delete({
  //       id: user1Entity2Id,
  //     });
  //     expect(secondResponse.results).toBeDefined();
  //     expect(secondResponse.results.success).toBe(true);
  //   });

  //   test("Delete user 2's entities", async () => {
  //     const firstResponse = await user2Client.entities.delete({
  //       id: user2Entity1Id,
  //     });
  //     expect(firstResponse.results).toBeDefined();
  //     expect(firstResponse.results.success).toBe(true);

  //     const secondResponse = await user2Client.entities.delete({
  //       id: user2Entity2Id,
  //     });
  //     expect(secondResponse.results).toBeDefined();
  //     expect(secondResponse.results.success).toBe(true);
  //   });

  test("REMOVE THIS, BUT A SUPER USER NEEDS TO DELETE THE ENTITIES FOR NOW", async () => {
    const firstResponse = await client.entities.delete({
      id: user1Entity1Id,
    });
    expect(firstResponse.results).toBeDefined();
    expect(firstResponse.results.success).toBe(true);

    const secondResponse = await client.entities.delete({
      id: user1Entity2Id,
    });
    expect(secondResponse.results).toBeDefined();
    expect(secondResponse.results.success).toBe(true);

    const thirdResponse = await client.entities.delete({
      id: user2Entity1Id,
    });
    expect(thirdResponse.results).toBeDefined();
    expect(thirdResponse.results.success).toBe(true);

    const fourthResponse = await client.entities.delete({
      id: user2Entity2Id,
    });
    expect(fourthResponse.results).toBeDefined();
    expect(fourthResponse.results.success).toBe(true);
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
