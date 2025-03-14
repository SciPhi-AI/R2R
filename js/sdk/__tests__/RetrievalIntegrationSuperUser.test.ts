import { r2rClient } from "../src/index";
import { describe, test, beforeAll, expect } from "@jest/globals";

const baseUrl = "http://localhost:7272";

const message = {
  role: "user" as const,
  content: "Tell me about Sonia.",
};

/**
 * sonia.txt will have an id of 28ce9a4c-4d15-5287-b0c6-67834b9c4546
 */
describe("r2rClient V3 Documents Integration Tests", () => {
  let client: r2rClient;
  let documentId: string;

  beforeAll(async () => {
    client = new r2rClient(baseUrl);
    await client.users.login({
      email: "admin@example.com",
      password: "change_me_immediately",
    });
  });

  async function readStream(
    stream: ReadableStream<Uint8Array>,
  ): Promise<string> {
    const reader = stream.getReader();
    let result = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) {
        break;
      }
      result += new TextDecoder().decode(value);
    }

    return result;
  }

  test("Create document with file path", async () => {
    const response = await client.documents.create({
      file: { path: "examples/data/sonia.txt", name: "sonia.txt" },
      metadata: { title: "sonia.txt" },
    });

    expect(response.results.documentId).toBeDefined();
    documentId = response.results.documentId;
  }, 10000);

  test("Search documents with no parameters", async () => {
    const response = await client.retrieval.search({ query: "Sonia" });

    expect(response.results).toBeDefined();
  });

  test("RAG with no parameters", async () => {
    const response = await client.retrieval.rag({ query: "Sonia" });

    expect(response.results).toBeDefined();
  }, 30000);

  test("Streaming RAG", async () => {
    const stream = await client.retrieval.rag({
      query: "Sonia",
      ragGenerationConfig: {
        stream: true,
      },
    });

    expect(stream).toBeInstanceOf(ReadableStream);
    const content = await readStream(stream);
    expect(content).toBeTruthy();
    expect(typeof content).toBe("string");
    expect(content.length).toBeGreaterThan(0);
  }, 30000);

  test("Agent with no parameters", async () => {
    const response = await client.retrieval.agent({
      message: message,
    });

    expect(response.results).toBeDefined();
  }, 30000);

  test("Streaming agent", async () => {
    const stream = await client.retrieval.agent({
      message: message,
      ragGenerationConfig: {
        stream: true,
      },
    });

    expect(stream).toBeInstanceOf(ReadableStream);
    const content = await readStream(stream);
    expect(content).toBeTruthy();
    expect(typeof content).toBe("string");
    expect(content.length).toBeGreaterThan(0);
  }, 30000);

  // test("Completion with no parameters", async () => {
  //   const response = await client.retrieval.completion({
  //     messages: messages,
  //   });

  //   expect(response.results).toBeDefined();
  // }, 30000);

  // test("Streaming Completion", async () => {
  //   const stream = await client.retrieval.completion({
  //     messages: messages,
  //     generation_config: {
  //       stream: true,
  //     },
  //   });

  //   expect(stream).toBeInstanceOf(ReadableStream);
  //   const content = await readStream(stream);
  //   expect(content).toBeTruthy();
  //   expect(typeof content).toBe("string");
  //   expect(content.length).toBeGreaterThan(0);
  // }, 30000);

  test("Get an agent answer with a task prompt override", async () => {
    const overrideMessage = {
      role: "user" as const,
      content: "What is the capital of France?",
    };

    const overridePrompt = "Antworte auf Deutsch.";

    const response = await client.retrieval.agent({
      message: overrideMessage,
      taskPrompt: overridePrompt,
      useSystemContext: false,
    });

    expect(response.results).toBeDefined();
    expect(response.results.messages.length).toBeGreaterThan(0);
    expect(response.results.messages[0].role).toBe("assistant");
    expect(response.results.messages[0].content).toContain("Paris");

    const germanWords = ["Die", "Hauptstadt", "von", "Frankreich", "ist"];
    const responseText = response.results.messages[0].content;
    expect(germanWords.some((word) => responseText.includes(word))).toBe(true);
  }, 30000);

  test("List and delete conversations", async () => {
    const listResponse = await client.conversations.list();
    expect(listResponse.results).toBeDefined();

    for (const conversation of listResponse.results) {
      const deleteResponse = await client.conversations.delete({
        id: conversation.id,
      });
      expect(deleteResponse.results).toBeDefined();
    }

    const finalListResponse = await client.conversations.list();
    expect(finalListResponse.results.length).toBe(0);
  });

  test("Delete document", async () => {
    const response = await client.documents.delete({ id: documentId });
    expect(response.results).toBeDefined();
  });
});
