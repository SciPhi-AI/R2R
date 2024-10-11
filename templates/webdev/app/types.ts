export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
  id?: string;
  timestamp?: number;
  isStreaming?: boolean;
  sources?: string | null;
  searchPerformed?: boolean;
}
