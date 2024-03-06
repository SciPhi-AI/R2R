export type Pipeline = {
  id: number;
  name: string;
  deployment_url: string;
  github_url: string;
  status: string;
  deployment: {
    id: number;
    uri: string;
  };
};

export type Provider = {
  id: number;
  name: string;
  type: string;
  logo: string;
};

export interface LogEntry {
  timestamp: string;
  pipeline_run_id: string;
  method: string;
  result:
    | string
    | searchResult[]
    | CompletionResult
    | ConstructPromptResult
    | ConstructContextResult;
  log_level: string;
  message: string;
}

export interface searchResult {
  id: string;
  score: number;
  text: string;
  // metadata: Metadata;
}

// # TODO - make eval dynamically selectable based on
// the configuration file of the pipeline

export interface evalResult {
  score: number;
  reason: string;
}

export interface evalResults {
  [key: string]: evalResult;
}
export interface Document {
  id: string;
  text: string;
  metadata: Object;
}

export interface EventSummary extends LogEntry {
  timestamp: string;
  pipelineRunId: string;
  pipelineRunType: string;
  method: string;
  searchQuery: string;
  searchResults: searchResult[];
  evalResults: evalResults | null;
  embeddingChunks: string | null;
  document: Document | null;
  completionResult: string;
  outcome: string;
  score: string;
}

export interface Metadata {
  tags: string | string[];
  text: string;
  document_id: string;
  pipeline_run_id: string;
}

export interface CompletionResult {
  id: string;
  choices: Choice[];
  created: number;
  model: string;
  object: string;
  system_fingerprint: string;
  usage: {
    completion_tokens: number;
    prompt_tokens: number;
    total_tokens: number;
  };
}

export interface Choice {
  finish_reason: string;
  index: number;
  logprobs: null | number;
  message: string;
}

export interface ConstructPromptResult {
  content: string;
}

export interface ConstructContextResult {
  content: string;
}

export interface LogsApiResponse {
  logs: LogEntry[];
}
