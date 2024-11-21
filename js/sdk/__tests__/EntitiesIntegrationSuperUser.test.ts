import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let entity1Id: string;
  let entity2Id: string;
  let entity3Id: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.users.login({
      email: "admin@example.com",
      password: "change_me_immediately",
    });
  });

  test("Create an entity", async () => {
    const response = await client.entities.create({
      name: "Entity 1",
      description: "The first entity",
    });
    expect(response.results).toBeDefined();
    entity1Id = response.results.id;
    expect(entity1Id).toEqual(response.results.id);
    expect(response.results.name).toEqual("Entity 1");
    expect(response.results.description).toBe("The first entity");
  });

  test("Create an entity with a category", async () => {
    const response = await client.entities.create({
      name: "Entity 2",
      description: "The second entity",
      category: "category",
    });
    entity2Id = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.name).toEqual("Entity 2");
    expect(response.results.description).toEqual("The second entity");
    expect(response.results.category).toEqual("category");
  });

  test("Ensure that there are two entities", async () => {
    const response = await client.entities.list();
    expect(response.results).toBeDefined();
    expect(response.results.length).toEqual(2);
  });

  test("Retrieve entity 1", async () => {
    const response = await client.entities.retrieve({ id: entity1Id });
    expect(response.results).toBeDefined();
    expect(response.results.name).toEqual("Entity 1");
    expect(response.results.description).toEqual("The first entity");
  });

  test("Retrieve entity 2", async () => {
    const response = await client.entities.retrieve({ id: entity2Id });
    expect(response.results).toBeDefined();
    expect(response.results.name).toEqual("Entity 2");
    expect(response.results.description).toEqual("The second entity");
    expect(response.results.category).toEqual("category");
  });

  test("Delete entity 1", async () => {
    const response = await client.entities.delete({ id: entity1Id });
    expect(response.results).toBeDefined();
    expect(response.results.success).toBe(true);
  });

  test("Delete entity 2", async () => {
    const response = await client.entities.delete({ id: entity2Id });
    expect(response.results).toBeDefined();
    expect(response.results.success).toBe(true);
  });

  test("Ensure that there are no entities", async () => {
    const response = await client.entities.list();
    expect(response.results).toBeDefined();
    expect(response.results.length).toEqual(0);
  });

  test("Create an entity", async () => {
    const response = await client.entities.create({
      name: "Entity 3",
      description: "The third entity",
    });
    expect(response.results).toBeDefined();
    entity3Id = response.results.id;
    expect(entity3Id).toEqual(response.results.id);
    expect(response.results.name).toEqual("Entity 3");
    expect(response.results.description).toBe("The third entity");
  });

  test("Ensure that there is only one entity now", async () => {
    const response = await client.entities.list();
    expect(response.results).toBeDefined();
    expect(response.results.length).toEqual(1);
  });

  test("Delete entity 3", async () => {
    const response = await client.entities.delete({ id: entity3Id });
    expect(response.results).toBeDefined();
    expect(response.results.success).toBe(true);
  });
});
