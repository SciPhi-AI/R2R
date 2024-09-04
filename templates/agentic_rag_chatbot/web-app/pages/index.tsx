'use client';
import React, { useState, useRef } from 'react';
import { ChatWindow } from '@/components/ChatWindow';
import { Search } from '@/components/Search';
import Header from '@/components/Header';

const Index: React.FC = () => {
  const [query, setQuery] = useState('');
  const [agentUrl] = useState(process.env.NEXT_PUBLIC_DEFAULT_AGENT_URL || '');
  const [isStreaming, setIsStreaming] = useState(false);

  const contentAreaRef = useRef<HTMLDivElement>(null);

  // Add this new state for messages
  const [messages, setMessages] = useState<any[]>([]);

  const handleClearMessages = () => {
    setMessages([]);
    setQuery('');
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Header />
      <div className="flex-grow">
        <div className="main-content-wrapper">
          <div className="main-content" ref={contentAreaRef}>
            <div className="w-full max-w-4xl mx-auto flex flex-col flex-grow overflow-auto">
              {/* Chat Interface */}
              <div className="flex-1 overflow-auto p-4">
                <ChatWindow
                  query={query}
                  setQuery={setQuery}
                  agentUrl={agentUrl}
                  messages={messages}
                  setMessages={setMessages}
                  isStreaming={isStreaming}
                  setIsStreaming={setIsStreaming}
                />
              </div>

              {/* Search Bar */}
              <div className="p-4 w-full">
                <Search
                  setQuery={setQuery}
                  placeholder="Start a conversation..."
                  onClear={handleClearMessages}
                  isStreaming={isStreaming}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Index;
