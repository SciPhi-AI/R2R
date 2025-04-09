const path = require('path');
const { r2rClient } = require("r2r-js");

// Create an account at SciPhi Cloud https://app.sciphi.ai and set an R2R_API_KEY environment variable
// or set the base URL to your instance. E.g. r2rClient("http://localhost:7272")
const client = new r2rClient("http://20.55.204.62:7272");

async function main() {
  const filePath = path.resolve(__dirname, "data/raskolnikov.txt");


  console.log("Ingesting file...");
  const ingestResult = await client.documents.create({
    file: {
      path: filePath,
      name: "raskolnikov.txt"
    },
    metadata: { author: "Dostoevsky" },
  });
  console.log("Ingest result:", JSON.stringify(ingestResult, null, 2));

  console.log("Waiting for the file to be ingested...");
  await new Promise((resolve) => setTimeout(resolve, 10000));

  console.log("Performing RAG...");
  const ragResponse = await client.retrieval.rag({
    query: "To whom was Raskolnikov desperately in debt to?",
  });

  console.log("Search Results:");
  ragResponse.results.searchResults.chunkSearchResults.forEach(
    (result, index) => {
      console.log(`\nResult ${index + 1}:`);
      console.log(`Text: ${result.text.substring(0, 100)}...`);
      console.log(`Score: ${result.score}`);
    },
  );

  console.log("\nCompletion:");
  console.log(ragResponse.results.completion);
}

main();
