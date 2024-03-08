import url from "url";

export default async function handler(req, res) {
  const queryObject = url.parse(req.url, true).query;
  // const apiKey = process.env.SCIPHI_API_KEY;

  const json_data = {
    query: queryObject.query,
    filters: {},
    limit: 10,
    settings: {},
    generation_config: { stream: true },
  };

  console.log(`Streaming response from: ${process.env.NEXT_PUBLIC_CLOUD_REMOTE_SERVER_URL}`)

  const externalApiResponse = await fetch(`${process.env.NEXT_PUBLIC_CLOUD_REMOTE_SERVER_URL}/rag_completion`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      // 'Authorization': `Bearer ${apiKey}`,
      Accept: "text/event-stream"
    },
    body: JSON.stringify(json_data)
  });

  res.setHeader('Content-Type', 'text/event-stream');
  res.setHeader('Cache-Control', 'no-cache');
  res.setHeader('Connection', 'keep-alive');

  const reader = externalApiResponse.body.getReader();
  while (true) {
    const { done, value } = await reader.read();
    console.log('streaming value = ', value);

    if (done) break;
    const text = new TextDecoder("utf-8").decode(value)
    console.log('text = ', text)
    res.write(text);
    res.flush();
  }

  res.end();
}
