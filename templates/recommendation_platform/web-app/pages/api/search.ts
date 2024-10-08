import { r2rClient, GenerationConfig } from "r2r-js";

export const config = {
  runtime: "edge",
};

interface RagParams {
  query: string;
  use_vector_search?: boolean;
  filters?: Record<string, any>;
  search_limit?: number;
  do_hybrid_search?: boolean;
  use_kg_search?: boolean;
  kg_agent_generation_config?: GenerationConfig;
}

export default async function handler(req: Request) {
  if (req.method !== "POST") {
    return new Response("Method Not Allowed", { status: 405 });
  }

  const { query, agentUrl } = await req.json();

  if (!agentUrl) {
    return new Response(JSON.stringify({ error: "Agent URL is required" }), {
      status: 400,
      headers: { "Content-Type": "application/json" },
    });
  }

  try {
    const client = new r2rClient(agentUrl);

    const params: RagParams = {
      query,
      use_vector_search: true,
      filters: {},
      search_limit: 10,
      do_hybrid_search: false,
      use_kg_search: false,
      kg_agent_generation_config: {
        temperature: 0.1,
        top_p: 1,
        top_k: 100,
        max_tokens_to_sample: 1024,
        stream: false,
      },
    };

    const search_results = await client.rag(params);

    return new Response(search_results, {
      headers: { "Content-Type": "text/plain" },
    });
  } catch (error: unknown) {
    console.error("Error in search:", error);
    return new Response(
      JSON.stringify({
        error: "Internal Server Error",
        details: error instanceof Error ? error.message : "Unknown error",
      }),
      {
        status: 500,
        headers: { "Content-Type": "application/json" },
      },
    );
  }
}
