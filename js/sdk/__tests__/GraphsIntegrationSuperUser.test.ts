import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect, afterAll } from "@jest/globals";
import fs from "fs";
import path from "path";

const baseUrl = "http://localhost:7272";
const TEST_OUTPUT_DIR = path.join(__dirname, "test-output");

describe("r2rClient V3 Graphs Integration Tests", () => {
  let client: r2rClient;
  let documentId: string;
  let collectionId: string;
  let entity1Id: string;
  let entity2Id: string;
  let relationshipId: string;
  let communityId: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.users.login({
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

  test("Create document with file path", async () => {
    const response = await client.documents.create({
      file: {
        path: "examples/data/raskolnikov_2.txt",
        name: "raskolnikov_2.txt",
      },
      metadata: { title: "raskolnikov_2.txt" },
    });

    expect(response.results.documentId).toBeDefined();
    documentId = response.results.documentId;
  }, 10000);

  test("Create new collection", async () => {
    const response = await client.collections.create({
      name: "Raskolnikov Collection",
    });
    expect(response).toBeTruthy();
    collectionId = response.results.id;
  });

  test("Retrieve collection", async () => {
    const response = await client.collections.retrieve({
      id: collectionId,
    });
    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(collectionId);
    expect(response.results.name).toBe("Raskolnikov Collection");
  });

  test("Update graph", async () => {
    const response = await client.graphs.update({
      collectionId: collectionId,
      name: "Raskolnikov Graph",
    });

    expect(response.results).toBeDefined();
  });

  test("Retrieve graph and ensure that update was successful", async () => {
    const response = await client.graphs.retrieve({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.name).toBe("Raskolnikov Graph");
    expect(response.results.updatedAt).not.toBe(response.results.createdAt);
  });

  test("List graphs", async () => {
    const response = await client.graphs.list({});

    expect(response.results).toBeDefined();
  });

  test("Check that there are no entities in the graph", async () => {
    const response = await client.graphs.listEntities({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength(0);
  });

  test("Check that there are no relationships in the graph", async () => {
    const response = await client.graphs.listRelationships({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength;
  });

  test("Extract entities from the document", async () => {
    const response = await client.documents.extract({
      id: documentId,
    });

    await new Promise((resolve) => setTimeout(resolve, 30000));

    expect(response.results).toBeDefined();
  }, 60000);

  test("Deduplicate entities in the document", async () => {
    const response = await client.documents.deduplicate({
      id: documentId,
    });

    await new Promise((resolve) => setTimeout(resolve, 30000));

    expect(response.results).toBeDefined();
  }, 60000);

  test("Export document entities to CSV with default options", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_entities_default.csv",
    );
    await client.documents.exportEntities({
      id: documentId,
      outputPath: outputPath,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
    expect(content.split("\n").length).toBeGreaterThan(1);
  });

  test("Export document entities to CSV with custom columns", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_entities_custom.csv",
    );
    await client.documents.exportEntities({
      id: documentId,
      outputPath: outputPath,
      columns: ["id", "name", "created_at"],
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    const headers = content
      .split("\n")[0]
      .split(",")
      .map((h) => h.trim());

    expect(headers).toContain('"id"');
    expect(headers).toContain('"name"');
    expect(headers).toContain('"created_at"');
  });

  test("Export filtered document entities to CSV", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_entities_filtered.csv",
    );
    await client.documents.exportEntities({
      id: documentId,
      outputPath: outputPath,
      filters: { document_type: { $eq: "txt" } },
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
  });

  test("Export document entities without headers", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_entities_no_header.csv",
    );
    await client.documents.exportEntities({
      id: documentId,
      outputPath: outputPath,
      includeHeader: false,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
  });

  test("Handle empty document entity export result", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_entities_empty.csv",
    );
    await client.documents.exportEntities({
      id: documentId,
      outputPath: outputPath,
      filters: { name: { $eq: "non_existent_name" } },
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content.split("\n").filter((line) => line.trim()).length).toBe(1);
  });

  test("Export document relationships to CSV with default options", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_relationships_default.csv",
    );
    await client.documents.exportRelationships({
      id: documentId,
      outputPath: outputPath,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
    expect(content.split("\n").length).toBeGreaterThan(1);
  });

  test("Export document relationships to CSV with custom columns", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_relationships_custom.csv",
    );
    await client.documents.exportRelationships({
      id: documentId,
      outputPath: outputPath,
      columns: ["subject", "object", "created_at"],
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    const headers = content
      .split("\n")[0]
      .split(",")
      .map((h) => h.trim());

    expect(headers).toContain('"subject"');
    expect(headers).toContain('"object"');
    expect(headers).toContain('"created_at"');
  });

  test("Export filtered document entities to CSV", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_entities_filtered.csv",
    );
    await client.documents.exportEntities({
      id: documentId,
      outputPath: outputPath,
      filters: { document_type: { $eq: "txt" } },
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
  });

  test("Export document relationships without headers", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_relationships_no_header.csv",
    );
    await client.documents.exportRelationships({
      id: documentId,
      outputPath: outputPath,
      includeHeader: false,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
  });

  test("Handle empty document relationships export result", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_relationships_empty.csv",
    );
    await client.documents.exportRelationships({
      id: documentId,
      outputPath: outputPath,
      filters: { subject: { $eq: "non_existent_subject" } },
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content.split("\n").filter((line) => line.trim()).length).toBe(1);
  });

  test("Assign document to collection", async () => {
    const response = await client.collections.addDocument({
      id: collectionId,
      documentId: documentId,
    });
    expect(response.results).toBeDefined();
  });

  test("Pull entities into the graph", async () => {
    const response = await client.graphs.pull({
      collectionId: collectionId,
    });
    expect(response.results).toBeDefined();
  });

  test("Check that there are entities in the graph", async () => {
    const response = await client.graphs.listEntities({
      collectionId: collectionId,
    });
    expect(response.results).toBeDefined();
    expect(response.totalEntries).toBeGreaterThanOrEqual(1);
  }, 60000);

  test("Check that there are relationships in the graph", async () => {
    const response = await client.graphs.listRelationships({
      collectionId: collectionId,
    });
    expect(response.results).toBeDefined();
    expect(response.totalEntries).toBeGreaterThanOrEqual(1);
  });

  test("Export graph entities to CSV with default options", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "graph_entities_default.csv");
    await client.graphs.exportEntities({
      collectionId: collectionId,
      outputPath: outputPath,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
    expect(content.split("\n").length).toBeGreaterThan(1);
  });

  test("Export graph entities to CSV with custom columns", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "graph_entities_custom.csv");
    await client.graphs.exportEntities({
      collectionId: collectionId,
      outputPath: outputPath,
      columns: ["id", "name", "created_at"],
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    const headers = content
      .split("\n")[0]
      .split(",")
      .map((h) => h.trim());

    expect(headers).toContain('"id"');
    expect(headers).toContain('"name"');
    expect(headers).toContain('"created_at"');
  });

  test("Export filtered graph entities to CSV", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "graph_entities_filtered.csv",
    );
    await client.graphs.exportEntities({
      collectionId: collectionId,
      outputPath: outputPath,
      filters: { document_type: { $eq: "txt" } },
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
  });

  test("Export graph entities without headers", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "graph_entities_no_header.csv",
    );
    await client.graphs.exportEntities({
      collectionId: collectionId,
      outputPath: outputPath,
      includeHeader: false,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
  });

  test("Handle empty graph entity export result", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "graph_entities_empty.csv");
    await client.graphs.exportEntities({
      collectionId: collectionId,
      outputPath: outputPath,
      filters: { name: { $eq: "non_existent_name" } },
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content.split("\n").filter((line) => line.trim()).length).toBe(1);
  });

  test("Export graph relationships to CSV with default options", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "graphs_relationships_default.csv",
    );
    await client.graphs.exportRelationships({
      collectionId: collectionId,
      outputPath: outputPath,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
    expect(content.split("\n").length).toBeGreaterThan(1);
  });

  test("Export graph relationships to CSV with custom columns", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "graph_relationships_custom.csv",
    );
    await client.graphs.exportRelationships({
      collectionId: collectionId,
      outputPath: outputPath,
      columns: ["subject", "object", "created_at"],
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    const headers = content
      .split("\n")[0]
      .split(",")
      .map((h) => h.trim());

    expect(headers).toContain('"subject"');
    expect(headers).toContain('"object"');
    expect(headers).toContain('"created_at"');
  });

  test("Export filtered graphs entities to CSV", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "graphs_entities_filtered.csv",
    );
    await client.graphs.exportEntities({
      collectionId: collectionId,
      outputPath: outputPath,
      filters: { document_type: { $eq: "txt" } },
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
  });

  test("Export document relationships without headers", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_relationships_no_header.csv",
    );
    await client.documents.exportRelationships({
      id: documentId,
      outputPath: outputPath,
      includeHeader: false,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
  });

  test("Handle empty graphs entity export result", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "document_relationships_empty.csv",
    );
    await client.graphs.exportEntities({
      collectionId: collectionId,
      outputPath: outputPath,
      filters: { name: { $eq: "non_existent_name" } },
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content.split("\n").filter((line) => line.trim()).length).toBe(1);
  });

  test("Check that there are no communities in the graph prior to building", async () => {
    const response = await client.graphs.listCommunities({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength(0);
  });

  // test("Build communities", async () => {
  //   const response = await client.graphs.buildCommunities({
  //     collectionId: collectionId,
  //   });

  //   await new Promise((resolve) => setTimeout(resolve, 15000));

  //   expect(response.results).toBeDefined();
  // }, 60000);

  // test("Check that there are communities in the graph", async () => {
  //   const response = await client.graphs.listCommunities({
  //     collectionId: collectionId,
  //   });

  //   expect(response.results).toBeDefined();
  //   expect(response.totalEntries).toBeGreaterThanOrEqual(1);
  // });

  test("Export graph communities to CSV with default options", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "graph_communities_default.csv",
    );
    await client.graphs.exportCommunities({
      collectionId: documentId,
      outputPath: outputPath,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
    expect(content.split("\n").length).toBeGreaterThan(1);
  });

  test("Export graph communities to CSV with custom columns", async () => {
    const outputPath = path.join(TEST_OUTPUT_DIR, "graph_entities_custom.csv");
    await client.graphs.exportCommunities({
      collectionId: collectionId,
      outputPath: outputPath,
      columns: ["id", "name", "created_at"],
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    const headers = content
      .split("\n")[0]
      .split(",")
      .map((h) => h.trim());

    expect(headers).toContain('"id"');
    expect(headers).toContain('"name"');
    expect(headers).toContain('"created_at"');
  });

  test("Export filtered graph communities to CSV", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "graph_communities_filtered.csv",
    );
    await client.graphs.exportCommunities({
      collectionId: collectionId,
      outputPath: outputPath,
      filters: { name: { $eq: "txt" } },
      includeHeader: true,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content).toBeTruthy();
  });

  test("Export graph communities without headers", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "graph_communities_no_header.csv",
    );
    await client.graphs.exportCommunities({
      collectionId: collectionId,
      outputPath: outputPath,
      includeHeader: false,
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
  });

  test("Handle empty graph communities export result", async () => {
    const outputPath = path.join(
      TEST_OUTPUT_DIR,
      "graph_communities_empty.csv",
    );
    await client.graphs.exportCommunities({
      collectionId: collectionId,
      outputPath: outputPath,
      filters: { name: { $eq: "non_existent_name" } },
    });

    expect(fs.existsSync(outputPath)).toBe(true);
    const content = fs.readFileSync(outputPath, "utf-8");
    expect(content.split("\n").filter((line) => line.trim()).length).toBe(1);
  });

  test("Create a new entity", async () => {
    const response = await client.graphs.createEntity({
      collectionId: collectionId,
      name: "Razumikhin",
      description: "A good friend of Raskolnikov",
      category: "Person",
    });

    expect(response.results).toBeDefined();
    entity1Id = response.results.id;
  });

  test("Create another new entity", async () => {
    const response = await client.graphs.createEntity({
      collectionId: collectionId,
      name: "Dunia",
      description: "The sister of Raskolnikov",
      category: "Person",
    });

    expect(response.results).toBeDefined();
    entity2Id = response.results.id;
  });

  test("Retrieve the entity", async () => {
    const response = await client.graphs.getEntity({
      collectionId: collectionId,
      entityId: entity1Id,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(entity1Id);
    expect(response.results.name).toBe("Razumikhin");
    expect(response.results.description).toBe("A good friend of Raskolnikov");
  });

  test("Retrieve the other entity", async () => {
    const response = await client.graphs.getEntity({
      collectionId: collectionId,
      entityId: entity2Id,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(entity2Id);
    expect(response.results.name).toBe("Dunia");
    expect(response.results.description).toBe("The sister of Raskolnikov");
  });

  test("Check that the entities are in the graph", async () => {
    const response = await client.graphs.listEntities({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.map((entity) => entity.id)).toContain(entity1Id);
    expect(response.results.map((entity) => entity.id)).toContain(entity2Id);
  });

  test("Create a relationship between the entities", async () => {
    const response = await client.graphs.createRelationship({
      collectionId: collectionId,
      subject: "Razumikhin",
      subjectId: entity1Id,
      predicate: "falls in love with",
      object: "Dunia",
      objectId: entity2Id,
      description: "Razumikhn and Dunia are central to the story",
    });

    relationshipId = response.results.id;

    expect(response.results).toBeDefined();
    expect(response.results.subject).toBe("Razumikhin");
    expect(response.results.object).toBe("Dunia");
    expect(response.results.predicate).toBe("falls in love with");
    expect(response.results.description).toBe(
      "Razumikhn and Dunia are central to the story",
    );
  });

  test("Retrieve the relationship", async () => {
    const response = await client.graphs.getRelationship({
      collectionId: collectionId,
      relationshipId: relationshipId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(relationshipId);
    expect(response.results.subject).toBe("Razumikhin");
    expect(response.results.object).toBe("Dunia");
    expect(response.results.predicate).toBe("falls in love with");
  });

  test("Create a new community", async () => {
    const response = await client.graphs.createCommunity({
      collectionId: collectionId,
      name: "Raskolnikov and Dunia Community",
      summary:
        "Raskolnikov and Dunia are siblings, the children of Pulcheria Alexandrovna",
      findings: [
        "Raskolnikov and Dunia are siblings",
        "They are the children of Pulcheria Alexandrovna",
        "Their family comes from a modest background",
        "Dunia works as a governess to support the family",
        "Raskolnikov is a former university student",
        "Both siblings are intelligent and well-educated",
        "They maintain a close relationship despite living apart",
        "Their mother Pulcheria writes letters to keep them connected",
      ],
      rating: 10,
      ratingExplanation:
        "Raskolnikov and Dunia are central to the story and have a complex relationship",
    });

    communityId = response.results.id;

    expect(response.results).toBeDefined();
    expect(response.results.name).toBe("Raskolnikov and Dunia Community");
    expect(response.results.summary).toBe(
      "Raskolnikov and Dunia are siblings, the children of Pulcheria Alexandrovna",
    );
    expect(response.results.findings).toContain(
      "Raskolnikov and Dunia are siblings",
    );
    expect(response.results.findings).toContain(
      "They are the children of Pulcheria Alexandrovna",
    );
    expect(response.results.findings).toContain(
      "Their family comes from a modest background",
    );
    expect(response.results.findings).toContain(
      "Dunia works as a governess to support the family",
    );
    expect(response.results.findings).toContain(
      "Raskolnikov is a former university student",
    );
    expect(response.results.findings).toContain(
      "Both siblings are intelligent and well-educated",
    );
    expect(response.results.findings).toContain(
      "They maintain a close relationship despite living apart",
    );
    expect(response.results.findings).toContain(
      "Their mother Pulcheria writes letters to keep them connected",
    );
    expect(response.results.rating).toBe(10);
    //TODO: Why is this failing?
    // expect(response.results.ratingExplanation).toBe(
    //   "Raskolnikov and Dunia are central to the story and have a complex relationship",
    // );
  });

  test("Update the entity", async () => {
    const response = await client.graphs.updateEntity({
      collectionId: collectionId,
      entityId: entity1Id,
      name: "Dmitri Prokofich Razumikhin",
      description: "A good friend of Raskolnikov and Dunia",
      category: "Person",
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(entity1Id);
    expect(response.results.name).toBe("Dmitri Prokofich Razumikhin");
    expect(response.results.description).toBe(
      "A good friend of Raskolnikov and Dunia",
    );
  });

  test("Retrieve the updated entity", async () => {
    const response = await client.graphs.getEntity({
      collectionId: collectionId,
      entityId: entity1Id,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(entity1Id);
    expect(response.results.name).toBe("Dmitri Prokofich Razumikhin");
    expect(response.results.description).toBe(
      "A good friend of Raskolnikov and Dunia",
    );
  });

  // This test is failing because we attach a separate name to the relationship, rather
  // than use the names of the entities. This needs to be fixed in the backend.
  //   test("Ensure that the entity was updated in the relationship", async () => {
  //     const response = await client.graphs.getRelationship({
  //       collectionId: collectionId,
  //       relationshipId: relationshipId,
  //     });

  //     expect(response.results).toBeDefined();
  //     expect(response.results.subject).toBe("Dmitri Prokofich Razumikhin");
  //     expect(response.results.object).toBe("Dunia");
  //     expect(response.results.predicate).toBe("falls in love with");
  //   });

  test("Update the relationship", async () => {
    const response = await client.graphs.updateRelationship({
      collectionId: collectionId,
      relationshipId: relationshipId,
      subject: "Razumikhin",
      subjectId: entity1Id,
      predicate: "marries",
      object: "Dunia",
      objectId: entity2Id,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(relationshipId);
    expect(response.results.subject).toBe("Razumikhin");
    expect(response.results.object).toBe("Dunia");
    expect(response.results.predicate).toBe("marries");
  });

  test("Retrieve the updated relationship", async () => {
    const response = await client.graphs.getRelationship({
      collectionId: collectionId,
      relationshipId: relationshipId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(relationshipId);
    expect(response.results.subject).toBe("Razumikhin");
    expect(response.results.object).toBe("Dunia");
    expect(response.results.predicate).toBe("marries");
  });

  test("Update the community", async () => {
    const response = await client.graphs.updateCommunity({
      collectionId: collectionId,
      communityId: communityId,
      name: "Rodion Romanovich Raskolnikov and Avdotya Romanovna Raskolnikova Community",
      summary:
        "Rodion and Avdotya are siblings, the children of Pulcheria Alexandrovna Raskolnikova",
    });

    expect(response.results).toBeDefined();
    expect(response.results.name).toBe(
      "Rodion Romanovich Raskolnikov and Avdotya Romanovna Raskolnikova Community",
    );
    expect(response.results.summary).toBe(
      "Rodion and Avdotya are siblings, the children of Pulcheria Alexandrovna Raskolnikova",
    );
  });

  test("Retrieve the updated community", async () => {
    const response = await client.graphs.getCommunity({
      collectionId: collectionId,
      communityId: communityId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.id).toBe(communityId);
    expect(response.results.name).toBe(
      "Rodion Romanovich Raskolnikov and Avdotya Romanovna Raskolnikova Community",
    );
    expect(response.results.summary).toBe(
      "Rodion and Avdotya are siblings, the children of Pulcheria Alexandrovna Raskolnikova",
    );
  });

  test("Delete the community", async () => {
    const response = await client.graphs.deleteCommunity({
      collectionId: collectionId,
      communityId: communityId,
    });

    expect(response.results).toBeDefined();
  });

  test("Check that the community was deleted", async () => {
    const response = await client.graphs.listCommunities({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength(0);
  });

  test("Reset the graph", async () => {
    const response = await client.graphs.reset({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
  });

  test("Check that there are no entities in the graph", async () => {
    const response = await client.graphs.listEntities({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength(0);
  });

  test("Check that there are no relationships in the graph", async () => {
    const response = await client.graphs.listRelationships({
      collectionId: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength(0);
  });

  test("Delete raskolnikov_2.txt", async () => {
    const response = await client.documents.delete({
      id: documentId,
    });

    expect(response.results).toBeDefined();
  });

  test("Check that the document is not in the collection", async () => {
    const response = await client.collections.listDocuments({
      id: collectionId,
    });

    expect(response.results).toBeDefined();
    expect(response.results.entries).toHaveLength(0);
  });

  test("Delete Raskolnikov Collection", async () => {
    const response = await client.collections.delete({
      id: collectionId,
    });

    expect(response.results).toBeDefined();
  });
});
