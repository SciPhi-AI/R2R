import React, { FC, useEffect, useState, useRef, useCallback } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Info, X } from 'lucide-react';
import posthog from 'posthog-js';

import MessageBubble from '@/components/MessageBubble';
import { Answer } from '@/components/Answer';
import { DefaultQueries } from '@/components/DefaultQueries';

const FUNCTION_START_TOKEN = '<function_call>';
const FUNCTION_END_TOKEN = '</function_call>';
const LLM_START_TOKEN = '<completion>';
const LLM_END_TOKEN = '</completion>';

interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
  id: string;
  timestamp: number;
  isStreaming?: boolean;
  sources?: Record<string, string | null>;
  searchPerformed?: boolean;
}

interface ChatWindowProps {
  query: string;
  setQuery: (query: string) => void;
  agentUrl: string;
  messages: Message[];
  setMessages: React.Dispatch<React.SetStateAction<Message[]>>;
  isStreaming: boolean;
  setIsStreaming: React.Dispatch<React.SetStateAction<boolean>>;
}

export const ChatWindow: FC<ChatWindowProps> = ({
  query,
  setQuery,
  agentUrl,
  messages,
  setMessages,
  isStreaming,
  setIsStreaming,
}) => {
  const [isSearching, setIsSearching] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [showInfoAlert, setShowInfoAlert] = useState(true);
  const [showInfoAlertDesc, setShowInfoAlertDesc] = useState(true);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  useEffect(() => {
    if (messages.length > 0) {
      scrollToBottom();
    }
  }, [messages, scrollToBottom]);

  const updateLastMessage = useCallback(
    (
      content?: string,
      sources?: Record<string, string | null>,
      isStreaming?: boolean,
      searchPerformed?: boolean
    ) => {
      setMessages((prevMessages) => {
        const updatedMessages = [...prevMessages];
        const lastMessage = updatedMessages[updatedMessages.length - 1];
        if (lastMessage.role === 'assistant') {
          return [
            ...updatedMessages.slice(0, -1),
            {
              ...lastMessage,
              ...(content !== undefined && { content }),
              ...(sources !== undefined && { sources }),
              ...(isStreaming !== undefined && { isStreaming }),
              ...(searchPerformed !== undefined && { searchPerformed }),
            },
          ];
        }
        return prevMessages;
      });
    },
    [setMessages]
  );

  useEffect(() => {
    if (!query || isStreaming) {
      return;
    }

    // setShowInfoAlert(false);
    setShowInfoAlertDesc(false);
    const parseStreaming = async () => {
      setIsStreaming(true);
      setIsSearching(true);
      setError(null);

      const newUserMessage: Message = {
        role: 'user',
        content: query,
        id: Date.now().toString(),
        timestamp: Date.now(),
        sources: {},
      };

      const newAssistantMessage: Message = {
        role: 'assistant',
        content: '',
        id: (Date.now() + 1).toString(),
        timestamp: Date.now() + 1,
        isStreaming: true,
        sources: {},
        searchPerformed: false,
      };

      setMessages((prevMessages) => [
        ...prevMessages,
        newUserMessage,
        newAssistantMessage,
      ]);

      let buffer = '';
      let inLLMResponse = false;
      let fullContent = '';

      const startTime = Date.now();
      let firstChunkTime: number | null = null;

      try {
        const response = await fetch('/api/agent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: [...messages, newUserMessage],
            apiUrl: agentUrl,
            use_vector_search: true,
            filters: {},
            search_limit: 20,
            do_hybrid_search: false,
            use_kg_search: true,
            rag_generation_config: {
              stream: true,
            },
          }),
        });

        const reader = response.body!.getReader();
        const decoder = new TextDecoder();

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            break;
          }

          if (firstChunkTime === null) {
            firstChunkTime = Date.now();
            posthog.capture('first_chunk_received', {
              time_to_first_chunk: firstChunkTime - startTime,
            });
          }

          buffer += decoder.decode(value, { stream: true });
          if (buffer.includes("</kg_search>")) {
            const [results, rest] = buffer.split("</kg_search>");

            console.log('results = ', results);
            const vectorSearchSources = results.includes('<search>')
              ? results.split('<search>')[1].split('</search>')[0]
              : null;

            const kgSearchResult = results.includes('<kg_search>')
              ? results.split('<kg_search>')[1].split('</kg_search>')[0]
              : null;

            updateLastMessage(
              undefined,
              { vector: vectorSearchSources, kg: kgSearchResult },
              undefined,
              true
            );
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

            fullContent += chunk;
            updateLastMessage(fullContent, undefined, true);
          }
        }
        posthog.capture('llm_response_complete', {
          total_response_time: Date.now() - startTime,
          response_content: fullContent,
        });
      } catch (err: unknown) {
        posthog.capture('llm_response_error', {
          error: err instanceof Error ? err.message : String(err),
        });
        console.error('Error in streaming:', err);
        setError(err instanceof Error ? err.message : String(err));
      } finally {
        setIsStreaming(false);
        setIsSearching(false);
        updateLastMessage(fullContent, undefined, false);
        setQuery('');
      }
    };

    parseStreaming();
  }, [
    query,
    agentUrl,
    setMessages,
    setIsStreaming,
    messages,
    updateLastMessage,
    isStreaming,
    setQuery,
  ]);

  return (
    <div className="flex flex-col h-full">
      {/* Info Alert */}
      {showInfoAlert && (
        <Alert className="flex flex-col items-start p-4 col-span-full relative border border-gray-300 rounded-lg shadow-lg mb-4">
          <div className="flex items-center mb-2">
            <Info className="h-6 w-6 text-blue-500 mr-2" />
            <AlertTitle className="text-lg font-semibold mt-2">
              Powered by R2R&apos;s GraphRAG —
              <a
                href="https://r2r-docs.sciphi.ai/cookbooks/graphrag"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500"
              >
                Learn how to implement your own GraphRAG here!
              </a>
            </AlertTitle>
          </div>
          {showInfoAlertDesc && (
            <AlertDescription className="text-sm text-left mb-2">
              GraphRAG excels at answering complex questions that other methods
              of search struggle with. By developing deep understanding of
              complex datasets and their relationships, GraphRAG can provide
              more accurate and informative answers to your users.
              <br /> <br />
              Learn more about GraphRAG from&nbsp;
              <a
                href="https://microsoft.github.io/graphrag/"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500"
              >
                Microsoft&apos;s research
              </a>
              &nbsp;or from our blog post on&nbsp;
              <a
                href="https://www.sciphi.ai/blog/graphrag"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500"
              >
                production ready GrapRAG.
              </a>
              <br /> <br />
              Here, we&apos;ve connected to am R2R server and built a knowledge
              graph over the profiles of the YC S24 companies. Feel free to ask
              any questions you have about the companies, their founders, or
              anything else you&apos;d like to know!
            </AlertDescription>
          )}
          <button
            className="absolute top-2 right-2 text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 rounded-full"
            onClick={() => setShowInfoAlert(false)}
          >
            <X className="h-4 w-4" />
          </button>
        </Alert>
      )}

      {/* Chat Messages */}
      <div className="flex-grow overflow-auto">
        <div className="flex flex-col space-y-8 mb-4">
          {messages.map((message, index) => (
            <React.Fragment key={message.id}>
              {message.role === 'user' ? (
                <MessageBubble message={message} />
              ) : (
                <Answer
                  message={message}
                  isStreaming={message.isStreaming || false}
                  isSearching={index === messages.length - 1 && isSearching}
                />
              )}
            </React.Fragment>
          ))}
          <div ref={messagesEndRef} />
        </div>
        {error && <div className="text-red-500">Error: {error}</div>}
        {messages.length === 0 && <DefaultQueries setQuery={setQuery} />}
      </div>
    </div>
  );
};
