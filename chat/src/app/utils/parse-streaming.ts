import { Source } from "@/app/interfaces/source";

const COMPLETION_START = "<completion>";
const COMPLETION_END = "</completion>"; 
const SEARCH_START = "<search>";
const SEARCH_END = "</search>";

const markdownParse = (text: string) => {
    return text.replace(/\[\[([cC])itation/g, "[citation")
      .replace(/[cC]itation:(\d+)]]/g, "citation:$1]")
      .replace(/\[\[([cC]itation:\d+)]](?!])/g, `[$1]`)
      .replace(/\[[cC]itation:(\d+)]/g, "[citation]($1)")
      .replace("\n","\\n")
};


export const parseStreaming = async (
  controller: AbortController,
  query: string,
  search_uuid: string,
  onSources: (value: Source[]) => void,
  onMarkdown: (value: string) => void,
  onError?: (status: number) => void,
) => {
  const response = await fetch(`/api/query?query=${query}`, {
    method: "GET",
    headers: {
      'Content-Type': 'application/json',
      Accept: "text/event-stream"
    },
  });

  if (response.status !== 200) {
    onError?.(response.status);
    return;
  }
  if (!response.body) {
    return;
  }

  const reader = response.body.getReader();
  let decoder = new TextDecoder();
  let completion = {
    'markdown': '',
    'streaming': false,
  }
  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);
    if (chunk.includes(SEARCH_END)) {
      const searchResultPayload = chunk.split(SEARCH_START)[1].split(SEARCH_END)[0]
      const parsedPayload = JSON.parse(searchResultPayload);
      const sources: Source[] = parsedPayload.map((item: any) => ({
        id: item.id,
        score: item.score,
        text: item.metadata.text,
        metadata: item.metadata,
      }));
    
      onSources(sources);
    }

    if (chunk.includes(COMPLETION_START)) {
      completion['markdown'] += chunk.split(COMPLETION_START)[1];
      completion['streaming'] = true
      onMarkdown(markdownParse(completion['markdown']))
    } else if (completion['streaming']) {
      completion['markdown'] += chunk.split(COMPLETION_END)[0];
      onMarkdown(markdownParse(completion['markdown']))
    }
    if (chunk.includes(COMPLETION_END)) {
      completion['streaming'] = false
    }
  }
};