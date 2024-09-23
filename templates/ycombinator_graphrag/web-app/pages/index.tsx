'use client';

import React, { useState, useRef, useEffect } from 'react';
import { useRouter } from 'next/router';
import { ChatWindow } from '@/components/ChatWindow';
import { Search } from '@/components/Search';
import Header from '@/components/Header';

const Index: React.FC = () => {
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [agentUrl] = useState('https://infra.sciphi.ai');
  // const [agentUrl] = useState('http://0.0.0.0:7272');
  const [isStreaming, setIsStreaming] = useState(false);
  const contentAreaRef = useRef<HTMLDivElement>(null);
  const [messages, setMessages] = useState<any[]>([]);

  useEffect(() => {
    if (router.isReady) {
      const { q } = router.query;
      if (typeof q === 'string') {
        setQuery(q);
      }
    }
  }, [router.isReady, router.query]);

  const handleClearMessages = () => {
    setMessages([]);
    setQuery('');
    router.push('/', undefined, { shallow: true });
  };

  const handleSearch = (newQuery: string) => {
    setQuery(newQuery);
    router.push(`/?q=${encodeURIComponent(newQuery)}`, undefined, {
      shallow: true,
    });
    // Add your search logic here
  };

  const clearUrlAndReload = () => {
    setQuery('');
    setMessages([]);
    router.push('/', undefined, { shallow: true }).then(() => {
      window.location.reload();
    });
  };

  return (
    <div className="flex flex-col min-h-screen">
      <Header onLogoClick={clearUrlAndReload} />
      <div className="flex-grow flex justify-center">
        <div className="w-full max-w-4xl flex flex-col h-full mt-24">
          <div className="flex-grow overflow-auto p-4">
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
        </div>
      </div>
      <div
        className="p-4 shadow-md sticky bottom-0"
        style={{ background: 'var(--background)' }}
      >
        <div className="flex justify-center">
          <div className="w-full max-w-4xl">
            <Search
              setQuery={handleSearch}
              placeholder="Start a conversation..."
              onClear={handleClearMessages}
              isStreaming={isStreaming}
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Index;
