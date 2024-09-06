const { r2rClient } = require("r2r-js");

// http://localhost:7272 or the address that you are running the R2R server
const client = new r2rClient("http://localhost:7272");

async function main() {
  const EMAIL = "admin@example.com";
  const PASSWORD = "change_me_immediately";
  console.log("Logging in...");
  await client.login(EMAIL, PASSWORD);

  const files = [
    { path: "examples/data/raskolnikov.txt", name: "raskolnikov.txt" },
  ];

  console.log("Ingesting file...");
  const ingestResult = await client.ingestFiles(files, {
    metadatas: [{ title: "raskolnikov.txt" }],
  });
  console.log("Ingest result:", JSON.stringify(ingestResult, null, 2));

  console.log("Performing RAG...");
  const ragResponse = await client.rag({
    query: "What does the file talk about?",
    rag_generation_config: {
      model: "gpt-4o",
      temperature: 0.0,
      stream: false,
    },
  });

  console.log("Search Results:");
  ragResponse.results.search_results.vector_search_results.forEach(
    (result, index) => {
      console.log(`\nResult ${index + 1}:`);
      console.log(`Text: ${result.metadata.text.substring(0, 100)}...`);
      console.log(`Score: ${result.score}`);
    },
  );

  console.log("\nCompletion:");
  console.log(ragResponse.results.completion.choices[0].message.content);

  console.log("Logging out...");
  await client.logout();
}

main();
