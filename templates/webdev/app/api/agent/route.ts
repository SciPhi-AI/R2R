import { NextRequest, NextResponse } from "next/server";
import { r2rClient } from "r2r-js";

const client = new r2rClient("http://localhost:8000");

export async function POST(request: NextRequest) {
  const { query } = await request.json();

  try {
    // Login with each request. In a production app, you'd want to manage sessions.
    await client.login("admin@example.com", "change_me_immediately");

    const vector_search_settings = {
      use_vector_search: true,
      // filters: { // Use the filters if you have specific document(s) you want to restrict your search to
      //   document_id: { eq: "3e157b3a-8469-51db-90d9-52e7d896b49b" },
      // },
      search_limit: 20,
      use_hybrid_search: true,
    };

    const rag_generation_config = {
      stream: false,
      temperature: 0.7,
      max_tokens: 150,
    };

    //You might consider passing in a string of prior conversation in a format like this:

  //   const messages=[
  //     {"role": "user", "content": "Who is the greatest philospher of all time?"},
  //     {"role": "assistant", "content": "Aristotle is widely considered the greatest philospher of all time."},
  //     {"role": "user", "content": query}
  // ]

  // For now, lets just pass in the one you provided:
    const messages = [
      {"role": "user", "content": query}
    ]

    const response = await client.agent(
      messages,
      vector_search_settings,
      rag_generation_config
    );

    return NextResponse.json({
      message: response.results
    });
  } catch (error: any) {
    return NextResponse.json(
      { message: error instanceof Error ? error.message : "An error occurred" },
      { status: 500 }
    );
  }
}
