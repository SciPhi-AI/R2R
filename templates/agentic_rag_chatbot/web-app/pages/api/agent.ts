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
    } = await req.json();

    if (!messages || !apiUrl) {
      return new Response('Missing required parameters', { status: 400 });
    }

    const client = new r2rClient(apiUrl);

    const searchParams = {
      use_vector_search: use_vector_search ?? true,
      filters: userId ? { ...filters, user_id: userId } : filters,
      limit: search_limit || 10,
      do_hybrid_search: do_hybrid_search ?? false,
    };

    const kgSearchParams = use_kg_search ? {} : undefined;

    const ragConfig = {
      ...rag_generation_config,
      stream: true,
    };

    const streamResponse = await client.agent(
      messages,
      searchParams,
      kgSearchParams,
      ragConfig
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
