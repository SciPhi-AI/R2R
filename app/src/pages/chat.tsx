'use client';
import { useSearchParams } from 'next/navigation';
import React, { useState, useEffect, useRef } from 'react';

import { Result } from '@/components/ChatDemo/result';
import { Search } from '@/components/ChatDemo/search';
import useSwitchManager from '@/components/ChatDemo/SwitchManager';
import Layout from '@/components/Layout';
import Sidebar from '@/components/Sidebar';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useToast } from '@/components/ui/use-toast';
import { useUserContext } from '@/context/UserContext';

const Index: React.FC = () => {
  const searchParams = useSearchParams();
  const { toast } = useToast();
  const [query, setQuery] = useState('');
  const [hasAttemptedFetch, setHasAttemptedFetch] = useState(false);
  const [searchLimit, setSearchLimit] = useState(10);
  const [searchFilters, setSearchFilters] = useState('{}');
  const [mode, setMode] = useState<'rag' | 'rag_agent'>('rag_agent');
  const [sidebarIsOpen, setSidebarIsOpen] = useState(false);

  useEffect(() => {
    if (searchParams) {
      setQuery(decodeURIComponent(searchParams.get('q') || ''));
    }
  }, [searchParams]);

  const { pipeline, getClient, selectedModel } = useUserContext();

  const toggleSidebar = () => {
    setSidebarIsOpen(!sidebarIsOpen);
  };

  const [isLoading, setIsLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('query');

  const { switches, initializeSwitch, updateSwitch } = useSwitchManager();

  const [temperature, setTemperature] = useState(0.1);
  const [topP, setTopP] = useState(1);
  const [top_k, setTop_k] = useState(100);
  const [max_tokens_to_sample, setMax_tokens_to_sample] = useState(1024);
  const [kg_temperature, setKgTemperature] = useState(0.1);
  const [kg_top_p, setKgTopP] = useState(1);
  const [kg_top_k, setKgTop_k] = useState(100);
  const [kg_max_tokens_to_sample, setKgMax_tokens_to_sample] = useState(1024);

  const [graphDimensions, setGraphDimensions] = useState({
    width: 0,
    height: 0,
  });
  const contentAreaRef = useRef<HTMLDivElement>(null);
  const [uploadedDocuments, setUploadedDocuments] = useState<string[]>([]);

  const [userId, setUserId] = useState(null);

  useEffect(() => {
    setQuery('');
  }, [mode]);

  useEffect(() => {
    initializeSwitch(
      'vector_search',
      true,
      'Vector Search',
      'Vector search is a search method that uses vectors to represent documents and queries. It is used to find similar documents to a given query.'
    );
    initializeSwitch(
      'hybrid_search',
      false,
      'Hybrid Search',
      'Hybrid search is a search method that combines multiple search methods to provide more accurate and relevant search results.'
    );
  }, [initializeSwitch]);

  const handleSwitchChange = (id: string, checked: boolean) => {
    updateSwitch(id, checked);
    toast({
      title: `${switches[id].label} status changed`,
      description: (
        <pre className="mt-2 mb-2 w-[340px] rounded-md bg-slate-950 p-4">
          <code className="text-white">
            {JSON.stringify({ [id]: checked }, null, 2)}
          </code>
        </pre>
      ),
    });
  };

  useEffect(() => {
    const fetchDocuments = async () => {
      if (pipeline) {
        try {
          const client = await getClient();
          if (!client) {
            throw new Error('Failed to get authenticated client');
          }
          setIsLoading(true);
          const documents = await client.documentsOverview();
          setUploadedDocuments(documents['results']);
        } catch (error) {
          console.error('Error fetching user documents:', error);
        } finally {
          setIsLoading(false);
          setHasAttemptedFetch(true);
        }
      }
    };

    fetchDocuments();
  }, [pipeline, getClient]);

  useEffect(() => {
    const updateDimensions = () => {
      if (contentAreaRef.current) {
        setGraphDimensions({
          width: contentAreaRef.current.offsetWidth,
          height: contentAreaRef.current.offsetHeight,
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);

    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  const safeJsonParse = (jsonString: string) => {
    try {
      return JSON.parse(jsonString);
    } catch (error) {
      console.warn('Invalid JSON input:', error);
      return {};
    }
  };

  return (
    <Layout pageTitle="Chat" includeFooter={false}>
      <div className="flex h-[calc(100vh)] pt-16">
        <Sidebar
          isOpen={sidebarIsOpen}
          onToggle={toggleSidebar}
          switches={switches}
          handleSwitchChange={handleSwitchChange}
          searchLimit={searchLimit}
          setSearchLimit={setSearchLimit}
          searchFilters={searchFilters}
          setSearchFilters={setSearchFilters}
          selectedModel={selectedModel}
          top_k={top_k}
          setTop_k={setTop_k}
          max_tokens_to_sample={max_tokens_to_sample}
          setMax_tokens_to_sample={setMax_tokens_to_sample}
          temperature={temperature}
          setTemperature={setTemperature}
          topP={topP}
          setTopP={setTopP}
        />

        {/* Main Content */}
        <div
          className={`main-content-wrapper ${sidebarIsOpen ? '' : 'sidebar-closed'}`}
        >
          <div
            className={`main-content ${sidebarIsOpen ? '' : 'sidebar-closed'}`}
            ref={contentAreaRef}
          >
            {/* Mode Selector */}
            <div className="mode-selector h-0">
              <Select
                value={mode}
                onValueChange={(value) => setMode(value as 'rag' | 'rag_agent')}
              >
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Select Mode" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="rag_agent">RAG Agent</SelectItem>
                  <SelectItem value="rag">Question and Answer</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="w-full max-w-4xl flex flex-col flex-grow overflow-hidden">
              {/* Chat Interface */}
              <div className="flex-1 overflow-auto p-4 mt-16">
                <Result
                  query={query}
                  setQuery={setQuery}
                  model={selectedModel}
                  userId={userId}
                  pipelineUrl={pipeline?.deploymentUrl || ''}
                  search_limit={searchLimit}
                  search_filters={safeJsonParse(searchFilters)}
                  rag_temperature={temperature}
                  rag_topP={topP}
                  rag_topK={top_k}
                  rag_maxTokensToSample={max_tokens_to_sample}
                  uploadedDocuments={uploadedDocuments}
                  setUploadedDocuments={setUploadedDocuments}
                  switches={switches}
                  hasAttemptedFetch={hasAttemptedFetch}
                  mode={mode}
                />
              </div>

              {/* Search Bar */}
              <div className="p-4 w-full">
                <Search
                  pipeline={pipeline || undefined}
                  setQuery={setQuery}
                  placeholder={
                    mode === 'rag'
                      ? 'Ask a question...'
                      : 'Start a conversation...'
                  }
                  disabled={uploadedDocuments?.length === 0 && mode === 'rag'}
                />
              </div>
            </div>
          </div>
        </div>
      </div>
    </Layout>
  );
};

export default Index;
