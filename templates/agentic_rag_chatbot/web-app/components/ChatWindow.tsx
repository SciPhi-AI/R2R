import React, { FC, useEffect, useState, useRef, useCallback } from 'react';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Info, X } from 'lucide-react';

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
  sources?: string | null;
  searchPerformed?: boolean;
}

export const ChatWindow: FC<{
  query: string;
  setQuery: (query: string) => void;
  agentUrl: string;
  messages: any[];
  setMessages: React.Dispatch<React.SetStateAction<any[]>>;
  isStreaming: boolean;
  setIsStreaming: React.Dispatch<React.SetStateAction<boolean>>;
}> = ({
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
      sources?: string,
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
        return updatedMessages;
      });
    },
    [setMessages]
  );

  useEffect(() => {
    if (!query || isStreaming) {
      return;
    }

    setShowInfoAlert(false);

    const parseStreaming = async () => {
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
      let fullContent = '';

      try {
        const response = await fetch('/api/agent', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            messages: [...messages, newUserMessage],
            apiUrl: agentUrl,
            use_vector_search: true,
            filters: {},
            search_limit: 10,
            do_hybrid_search: false,
            use_kg_search: false,
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

          buffer += decoder.decode(value, { stream: true });

          if (buffer.includes(FUNCTION_END_TOKEN)) {
            const [results, rest] = buffer.split(FUNCTION_END_TOKEN);
            const sourcesContent = results
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

            fullContent += chunk;
            updateLastMessage(fullContent, undefined, true);
          }
        }
      } catch (err: unknown) {
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
    <div className="flex flex-col">
      {showInfoAlert && (
        <Alert className="flex flex-col items-start p-4 col-span-full relative border border-gray-300 rounded-lg shadow-lg">
          <div className="flex items-center mb-2">
            <Info className="h-6 w-6 text-blue-500 mr-2" />
            <AlertTitle className="text-lg font-semibold">
              You&apos;re testing out an R2R Template —
              <a
                href="https://sciphi.ai"
                target="_blank"
                rel="noopener noreferrer"
                className="text-blue-500"
              >
                Deploy it for yourself in just 5 minutes!
              </a>
            </AlertTitle>
          </div>
          <AlertDescription className="text-sm text-left mb-2">
            Using RAG in your production applications is easy with SciPhi!
            <br /> <br />
            Here, we&apos;ve connected to a SciPhi hosted R2R server and added
            some sample documents about retrieval augmented generation (RAG).
            Just like that, we&apos;re ready to go!
          </AlertDescription>
          <button
            className="absolute top-2 right-2 text-gray-400 hover:text-gray-600 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-gray-500 rounded-full"
            onClick={() => setShowInfoAlert(false)}
          >
            <X className="h-4 w-4" />
          </button>
        </Alert>
      )}
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
  );
};
