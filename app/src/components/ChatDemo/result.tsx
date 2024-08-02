import React, { FC, useEffect, useState, useRef } from 'react';

import { useUserContext } from '@/context/UserContext';
import { Message, RagGenerationConfig } from '@/types';

import { Answer } from './answer';
import { DefaultQueries } from './DefaultQueries';
import MessageBubble from './MessageBubble';
import { UploadButton } from './upload';

const FUNCTION_START_TOKEN = '<function_call>';
const FUNCTION_END_TOKEN = '</function_call>';
const SEARCH_START_TOKEN = '<search>';
const SEARCH_END_TOKEN = '</search>';
const LLM_START_TOKEN = '<completion>';
const LLM_END_TOKEN = '</completion>';

export const Result: FC<{
  query: string;
  setQuery: (query: string) => void;
  userId: string | null;
  pipelineUrl: string | null;
  search_limit: number;
  search_filters: Record<string, unknown>;
  rag_temperature: number | null;
  rag_topP: number | null;
  rag_topK: number | null;
  rag_maxTokensToSample: number | null;
  model: string | null;
  uploadedDocuments: string[];
  setUploadedDocuments: React.Dispatch<React.SetStateAction<string[]>>;
  hasAttemptedFetch: boolean;
  switches: any;
  mode: 'rag' | 'rag_agent';
}> = ({
  query,
  setQuery,
  userId,
  pipelineUrl,
  search_limit,
  search_filters,
  rag_temperature,
  rag_topP,
  rag_topK,
  rag_maxTokensToSample,
  model,
  uploadedDocuments,
  setUploadedDocuments,
  hasAttemptedFetch,
  switches,
  mode,
}) => {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(false);
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [isProcessingQuery, setIsProcessingQuery] = useState(false);
  const { getClient } = useUserContext();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMessages([]);
  }, [mode]);

  useEffect(() => {
    localStorage.setItem('chatMessages', JSON.stringify(messages));
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const parseStreaming = async (query: string): Promise<void> => {
    if (isProcessingQuery) {
      return;
    }
    setIsProcessingQuery(true);
    setIsStreaming(true);
    setIsSearching(true);
    setError(null);

    const newUserMessage: Message = {
      role: 'user',
      content: query,
      id: Date.now().toString(),
      timestamp: Date.now(),
    };

    const newAssistantMessage: Message = {
      role: 'assistant',
      content: '',
      id: (Date.now() + 1).toString(),
      timestamp: Date.now() + 1,
      isStreaming: true,
      sources: null,
      searchPerformed: false,
    };

    setMessages((prevMessages) => [
      ...prevMessages,
      newUserMessage,
      newAssistantMessage,
    ]);

    let buffer = '';
    let inLLMResponse = false;
    let sourcesContent = '';

    try {
      const client = await getClient();
      if (!client) {
        throw new Error('Failed to get authenticated client');
      }

      const ragGenerationConfig: RagGenerationConfig = {
        stream: true,
        temperature: rag_temperature ?? undefined,
        top_p: rag_topP ?? undefined,
        top_k: rag_topK ?? undefined,
        max_tokens_to_sample: rag_maxTokensToSample ?? undefined,
        model: model !== 'null' && model !== null ? model : undefined,
      };

      const streamResponse =
        mode === 'rag_agent'
          ? await client.agent({
              messages: [...messages, newUserMessage],
              use_vector_search: switches.vector_search?.checked ?? true,
              search_filters,
              search_limit,
              do_hybrid_search: switches.hybrid_search?.checked ?? false,
              use_kg_search: switches.knowledge_graph_search?.checked ?? false,
              rag_generation_config: ragGenerationConfig,
            })
          : await client.rag({
              query,
              use_vector_search: switches.vector_search?.checked ?? true,
              search_filters,
              search_limit,
              do_hybrid_search: switches.hybrid_search?.checked ?? false,
              use_kg_search: switches.knowledge_graph_search?.checked ?? false,
              rag_generation_config: ragGenerationConfig,
            });

      const reader = streamResponse.getReader();
      const decoder = new TextDecoder();

      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        if (mode === 'rag') {
          if (buffer.includes(SEARCH_END_TOKEN)) {
            const [results, rest] = buffer.split(SEARCH_END_TOKEN);
            sourcesContent = results.replace(SEARCH_START_TOKEN, '');
            updateLastMessage(undefined, sourcesContent);
            buffer = rest || '';
            setIsSearching(false);
          }

          if (buffer.includes(LLM_START_TOKEN)) {
            inLLMResponse = true;
            buffer = buffer.split(LLM_START_TOKEN)[1] || '';
          }

          if (inLLMResponse) {
            const endTokenIndex = buffer.indexOf(LLM_END_TOKEN);
            let chunk = '';

            if (endTokenIndex !== -1) {
              chunk = buffer.slice(0, endTokenIndex);
              buffer = buffer.slice(endTokenIndex + LLM_END_TOKEN.length);
              inLLMResponse = false;
            } else {
              chunk = buffer;
              buffer = '';
            }

            updateLastMessage(chunk);
          }
        } else {
          if (buffer.includes(FUNCTION_END_TOKEN)) {
            const [results, rest] = buffer.split(FUNCTION_END_TOKEN);
            sourcesContent = results
              .replace(FUNCTION_START_TOKEN, '')
              .replace(/^[\s\S]*?<results>([\s\S]*)<\/results>[\s\S]*$/, '$1');
            updateLastMessage(undefined, sourcesContent, undefined, true);
            buffer = rest || '';
            setIsSearching(false);
          }

          if (buffer.includes(LLM_START_TOKEN)) {
            inLLMResponse = true;
            buffer = buffer.split(LLM_START_TOKEN)[1] || '';
          }

          if (inLLMResponse) {
            const endTokenIndex = buffer.indexOf(LLM_END_TOKEN);
            let chunk = '';

            if (endTokenIndex !== -1) {
              chunk = buffer.slice(0, endTokenIndex);
              buffer = buffer.slice(endTokenIndex + LLM_END_TOKEN.length);
              inLLMResponse = false;
            } else {
              chunk = buffer;
              buffer = '';
            }

            updateLastMessage(chunk);
          }
        }
      }
    } catch (err: unknown) {
      console.error('Error in streaming:', err);
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setIsStreaming(false);
      setIsSearching(false);
      setIsProcessingQuery(false);
      updateLastMessage(undefined, undefined, false);
    }
  };

  const updateLastMessage = (
    content?: string,
    sources?: string,
    isStreaming?: boolean,
    searchPerformed?: boolean
  ) => {
    setMessages((prevMessages) => {
      const updatedMessages = [...prevMessages];
      const lastMessage = updatedMessages[updatedMessages.length - 1];
      if (lastMessage.role === 'assistant') {
        if (content !== undefined) {
          lastMessage.content += content;
        }
        if (sources !== undefined) {
          lastMessage.sources = sources;
        }
        if (isStreaming !== undefined) {
          lastMessage.isStreaming = isStreaming;
        }
        if (searchPerformed !== undefined) {
          lastMessage.searchPerformed = searchPerformed;
        }
      }
      return updatedMessages;
    });
  };

  useEffect(() => {
    if (query === '' || !pipelineUrl) {
      return;
    }

    const debouncedParseStreaming = setTimeout(() => {
      parseStreaming(query);
    }, 500);

    return () => clearTimeout(debouncedParseStreaming);
  }, [query, userId, pipelineUrl]);

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col space-y-8 mb-4">
        {messages.map((message, index) => (
          <React.Fragment key={message.id}>
            {message.role === 'user' ? (
              <MessageBubble message={message} />
            ) : (
              <Answer
                message={message}
                isStreaming={message.isStreaming || false}
                isSearching={
                  index === messages.length - 1 ? isSearching : false
                }
                mode={mode}
              />
            )}
          </React.Fragment>
        ))}
        <div ref={messagesEndRef} />
      </div>
      {error && <div className="text-red-500">Error: {error}</div>}
      {!query && <DefaultQueries setQuery={setQuery} mode={mode} />}
      {hasAttemptedFetch &&
        uploadedDocuments?.length === 0 &&
        pipelineUrl &&
        mode === 'rag' && (
          <div className="absolute inset-4 flex items-center justify-center backdrop-blur-sm">
            <div className="flex items-center p-4 bg-white shadow-2xl rounded text-blue-500 font-medium gap-4">
              Please upload at least one document to submit queries.{' '}
              <UploadButton
                userId={userId}
                uploadedDocuments={uploadedDocuments}
                setUploadedDocuments={setUploadedDocuments}
              />
            </div>
          </div>
        )}
    </div>
  );
};
