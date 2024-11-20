import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

describe("r2rClient V3 Collections Integration Tests", () => {
  let client: r2rClient;
  let graph1Id: string;
  let graph2Id: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.users.login({
      email: "admin@example.com",
      password: "change_me_immediately",
    });
  });

  test("Create a graph with only a name", async () => {
    const response = await client.graphs.create({
      name: "Graph 1",
    });
    expect(response.results).toBeDefined();
    graph1Id = response.results.id;
  });

  test("Create a graph with name and description", async () => {
    const response = await client.graphs.create({
      name: "2",
      description: "Graph 2",
    });
    console.log("Result from create graph 2", response);
    expect(response.results).toBeDefined();
  });

  test("Creating a graph that already exists will throw a 409", async () => {
    await expect(client.graphs.create({ name: "Graph 1" })).rejects.toThrow(
      /Status 409/,
    );
  });
});
