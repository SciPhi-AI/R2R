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
    expect(graph1Id).toEqual(response.results.id);
    expect(response.results.name).toEqual("Graph 1");
    expect(response.results.description).toBe("");
  });

  test("Create a graph with name and description", async () => {
    const response = await client.graphs.create({
      name: "2",
      description: "Graph 2",
    });
    graph2Id = response.results.id;
    expect(response.results).toBeDefined();
    expect(response.results.name).toEqual("2");
    expect(response.results.description).toEqual("Graph 2");
  });

  test("Ensure that there are two graphs", async () => {
    const response = await client.graphs.list();
    expect(response.results).toBeDefined();
    expect(response.results.length).toEqual(2);
  });

  test("Retrieve graph 1", async () => {
    const response = await client.graphs.retrieve({ id: graph1Id });
    expect(response.results).toBeDefined();
    expect(response.results.name).toEqual("Graph 1");
    expect(response.results.description).toBe("");
  });

  test("Retrieve graph 2", async () => {
    const response = await client.graphs.retrieve({ id: graph2Id });
    expect(response.results).toBeDefined();
    expect(response.results.name).toEqual("2");
    expect(response.results.description).toEqual("Graph 2");
  });

  test("Update the name of graph 1", async () => {
    const response = await client.graphs.update({
      id: graph1Id,
      name: "Graph 1 Updated",
    });
    expect(response.results).toBeDefined();
    expect(response.results.name).toEqual("Graph 1 Updated");
  });

  test("Update the description graph 2", async () => {
    const response = await client.graphs.update({
      id: graph2Id,
      description: "Graph 2 Updated",
    });
    expect(response.results).toBeDefined();
    expect(response.results.description).toEqual("Graph 2 Updated");
  });

  test("Delete graph 1", async () => {
    const response = await client.graphs.delete({ id: graph1Id });
    expect(response.results).toBeDefined();
    expect(response.results.success).toBe(true);
  });

  test("Delete graph 2", async () => {
    const response = await client.graphs.delete({ id: graph2Id });
    expect(response.results).toBeDefined();
    expect(response.results.success).toBe(true);
  });
});
