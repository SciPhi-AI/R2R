import { r2rClient } from 'r2r-js';

export const config = {
  runtime: 'edge',
};

export default async function handler(req: Request) {
  if (req.method !== 'POST') {
    return new Response('Method Not Allowed', { status: 405 });
  }

  try {
    const {
      messages,
      userId,
      apiUrl,
      use_vector_search,
      filters,
      search_limit,
      do_hybrid_search,
      use_kg_search,
      rag_generation_config,
      kg_search_type,
    } = await req.json();

    if (!messages || !apiUrl) {
      return new Response('Missing required parameters', { status: 400 });
    }

    const client = new r2rClient(apiUrl);

    const searchParams = {
      use_vector_search: use_vector_search ?? true,
      filters: userId ? { ...filters, user_id: userId } : filters,
      search_limit: 20, // search_limit || 20,
      do_hybrid_search: do_hybrid_search ?? false,
      use_kg_search: true, // use_kg_search ?? false,
      // kg_search_type: "local", // kg_search_type ?? 'local',
    };

    const kgSearchParams = use_kg_search
      ? { use_kg_search: true, kg_search_type: 'local' }
      : undefined;

    const ragConfig = {
      ...rag_generation_config,
      stream: true,
    };
    const taskPromptOverride = `
    ### You are a helpful agent that can search for information.


    When asked a question, perform a search to find relevant information and provide a response. Your dataset consits of information about companies from the latest YC batch, summer 2024.


    The response should contain line-item attributions to relevant search results, and be as informative if possible.

    If no relevant results are found, then state that no results were found.

    If no obvious question is present, then do not carry out a search, and instead ask for clarification.\

    REMINDER - Use line item references to like [1], [2], ... refer to specifically numbered items in the provided context.

    ALSO, NOTE - Above is combined output from a knowledge graph and search engine for YCombinator. PAY CLOSE ATTENTION TO THE KNOWLEDGE GRAPH RESULTS ABOVE, and give a detailed synthesis of the information in your response. ANY POOR RESPONSES WILL RESULT IN YOUR TERMINATION.
    `;
    const streamResponse = await client.agent(
      messages,
      searchParams,
      kgSearchParams,
      ragConfig,
      taskPromptOverride
    );

    return new Response(streamResponse, {
      headers: { 'Content-Type': 'text/event-stream' },
    });
  } catch (error: unknown) {
    console.error('Error in agent completion:', error);
    return new Response(
      JSON.stringify({
        error: 'Internal Server Error',
        details: error instanceof Error ? error.message : 'Unknown error',
      }),
      {
        status: 500,
        headers: { 'Content-Type': 'application/json' },
      }
    );
  }
}
