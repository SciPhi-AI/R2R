import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let entity1Id: string;
  let entity2Id: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.users.login({
      email: "admin@example.com",
      password: "change_me_immediately",
    });
  });

  test("Create an Entity", async () => {
    const response = await client.entities.create({
      name: "Entity 1",
      description: "The first entity",
    });
    console.log(response);
    expect(response.results).toBeDefined();
    entity1Id = response.results.id;
    expect(entity1Id).toEqual(response.results.id);
    expect(response.results.name).toEqual("Entity 1");
    expect(response.results.description).toBe("The first entity");
  });

  test("Create an Entity", async () => {
    const response = await client.entities.create({
      name: "Entity 2",
      description: "The second entity",
    });
    console.log(response);
    entity2Id = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.name).toEqual("Entity 2");
    expect(response.results.description).toEqual("The second entity");
  });
});
