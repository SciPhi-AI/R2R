import React, { useState, useEffect } from 'react';
import { FC } from 'react';
import Markdown from 'react-markdown';

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Skeleton } from '@/components/ui/skeleton';
import { Logo } from '@/components/Logo';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { SearchResults } from '@/components/SearchResults';
import { KGSearchResult, VectorSearchResult } from '@/types';

interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
  id?: string;
  timestamp?: number;
  isStreaming?: boolean;
  sources?: Record<string, string | null>;
  searchPerformed?: boolean;
}

interface Source extends VectorSearchResult {
  id: string;
  score: number;
  metadata: {
    title?: string;
    text?: string;
    documentid?: string;
    snippet?: string;
  };
}

const AnimatedEllipsis: FC = () => {
  const [dots, setDots] = useState('');

  useEffect(() => {
    const interval = setInterval(() => {
      setDots((prevDots) => (prevDots.length >= 3 ? '' : prevDots + '.'));
    }, 200);

    return () => clearInterval(interval);
  }, []);

  return (
    <span
      style={{
        color: 'black',
        display: 'inline-block',
        width: '1em',
        height: '1em',
        textAlign: 'left',
      }}
    >
      {dots}
    </span>
  );
};

function formatMarkdownNewLines(markdown: string): string {
  return markdown
    .replace(/\[(\d+)]/g, '[$1]($1)')
    .split(`"queries":`)[0]
    .replace(/\\u[\dA-F]{4}/gi, (match: string) =>
      String.fromCharCode(parseInt(match.replace(/\\u/g, ''), 16))
    );
}

const parseVectorSearchSources = (sources: string | object): Source[] => {
  if (typeof sources === 'string') {
    try {
      const cleanedSources = sources;
      return JSON.parse(cleanedSources);
    } catch (error) {
      console.error('Failed to parse sources:', error);
      return [];
    }
  }
  return sources as Source[];
};

const parseKGSearchResult = (sources: string | object): KGSearchResult[] => {
  if (typeof sources === 'string') {
    try {
      const cleanedSources = sources;
      return JSON.parse(cleanedSources);
    } catch (error) {
      console.error('Failed to parse sources:', error);
      return [];
    }
  }
  return sources as KGSearchResult[];
};

const SourceInfo: React.FC<{ isSearching: boolean; sourcesCount: number }> = ({
  isSearching,
  sourcesCount,
}) => (
  <div className="flex items-center justify-between w-full">
    <Logo width={50} height={50} disableLink={true} />
    <span className="text-sm font-normal text-black">
      {isSearching ? (
        <span className="searching-animation">Searching over sources...</span>
      ) : sourcesCount > 0 ? (
        `View ${sourcesCount} Sources`
      ) : (
        'No sources found'
      )}
    </span>
  </div>
);

export const Answer: FC<{
  message: Message;
  isStreaming: boolean;
  isSearching: boolean;
}> = ({ message, isStreaming, isSearching }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [parsedVectorSources, setParsedVectorSources] = useState<Source[]>([]);
  const [parsedEntities, setParsedEntities] = useState<KGSearchResult[]>([]);
  const [parsedCommunities, setParsedCommunities] = useState<KGSearchResult[]>(
    []
  );
  useEffect(() => {
    if (message.sources?.vector) {
      const parsed = parseVectorSearchSources(message.sources.vector);
      setParsedVectorSources(parsed);
    }

    if (message.sources?.kg) {
      console.log('message.sources.kg = ', message.sources.kg);
      let kgLocalResult: KGSearchResult[] = JSON.parse(message.sources.kg);

      const entitiesArray = kgLocalResult.filter(
        (item: any) => item.result_type === 'entity'
      );
      const communitiesArray = kgLocalResult.filter(
        (item: any) => item.result_type === 'community'
      );
      setParsedEntities(entitiesArray);
      setParsedCommunities(communitiesArray);
    }
  }, [message.sources]);

  const renderContent = () => {
    const paragraphs = message.content.split('\n\n');
    return paragraphs.map((paragraph, index) => (
      <Markdown
        key={index}
        components={{
          h1: (props) => <h1 className="black" {...props} />,
          h2: (props) => <h2 className="black" {...props} />,
          h3: (props) => <h3 style={{ color: 'black' }} {...props} />,
          h4: (props) => <h4 style={{ color: 'black' }} {...props} />,
          h5: (props) => <h5 style={{ color: 'black' }} {...props} />,
          h6: (props) => <h6 style={{ color: 'black' }} {...props} />,
          strong: (props) => (
            <strong style={{ color: 'black', fontWeight: 'bold' }} {...props} />
          ),
          p: ({ children }) => (
            <p style={{ color: 'black', display: 'inline' }}>
              {children}
              {isStreaming && index === paragraphs.length - 1 && (
                <AnimatedEllipsis />
              )}
            </p>
          ),
          li: (props) => <li style={{ color: 'black' }} {...props} />,
          blockquote: (props) => (
            <blockquote style={{ color: 'black' }} {...props} />
          ),
          em: (props) => <em style={{ color: 'black' }} {...props} />,
          code: (props) => <code style={{ color: 'black' }} {...props} />,
          pre: (props) => <pre style={{ color: 'black' }} {...props} />,
          a: ({ href, ...props }) => {
            if (!href) return null;
            const source = parsedVectorSources[+href - 1];
            if (!source) return null;
            const metadata = source.metadata;
            return (
              <span className="inline-block w-4">
                <Popover>
                  <PopoverTrigger asChild>
                    <span
                      title={metadata?.title}
                      className="inline-block cursor-pointer transform scale-[60%] no-underline font-medium w-6 text-center h-6 rounded-full origin-top-left"
                      style={{ background: 'var(--background)' }}
                    >
                      {href}
                    </span>
                  </PopoverTrigger>
                  <PopoverContent
                    align="start"
                    className="max-w-screen-md flex flex-col gap-2 bg-zinc-800 shadow-transparent ring-zinc-600 border-zinc-600 ring-4 text-xs"
                  >
                    <div className="text-zinc-200 text-ellipsis overflow-hidden whitespace-nowrap font-medium">
                      {metadata.title ? `Title: ${metadata.title}` : ''}
                      {metadata?.documentid
                        ? `, DocumentId: ${metadata.documentid.slice(0, 8)}`
                        : ''}
                    </div>
                    <div className="flex gap-4">
                      <div className="flex-1">
                        <div className="line-clamp-4 text-zinc-300 break-words">
                          {metadata?.snippet ?? ''}
                        </div>
                        <div className="line-clamp-4 text-zinc-300 break-words">
                          {source.text ?? ''}
                        </div>
                      </div>
                    </div>
                  </PopoverContent>
                </Popover>
              </span>
            );
          },
        }}
      >
        {formatMarkdownNewLines(paragraph)}
      </Markdown>
    ));
  };
  return (
    <div className="mt-4">
      <Accordion
        type="single"
        collapsible
        className="w-full"
        onValueChange={(value) => setIsOpen(value === 'answer')}
      >
        <AccordionItem value="answer">
          <AccordionTrigger className="py-2 text-lg font-bold text-zinc-200 hover:no-underline text-black">
            <SourceInfo
              isSearching={isSearching}
              sourcesCount={parsedVectorSources.length}
            />
          </AccordionTrigger>
          <AccordionContent>
            {!isSearching && parsedVectorSources.length > 0 && (
              <SearchResults
                vectorSearchResults={parsedVectorSources}
                entities={parsedEntities}
                communities={parsedCommunities}
              />
            )}
          </AccordionContent>
        </AccordionItem>
      </Accordion>

      <div className="space-y-4 mt-4">
        {message.content || isStreaming ? (
          <div className="prose prose-sm max-w-full text-zinc-300 overflow-y-auto max-h-[700px] prose-headings:text-white prose-p:text-white prose-strong:text-white prose-code:text-white bg-zinc-200 p-4 rounded-lg">
            {message.content ? (
              renderContent()
            ) : (
              <div
                style={{
                  color: 'black',
                  display: 'inline-block',
                  width: '1em',
                  height: '1em',
                }}
              >
                <AnimatedEllipsis />
              </div>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            <Skeleton className="max-w-lg h-4 bg-zinc-200" />
            <Skeleton className="max-w-2xl h-4 bg-zinc-200" />
            <Skeleton className="max-w-lg h-4 bg-zinc-200" />
            <Skeleton className="max-w-xl h-4 bg-zinc-200" />
          </div>
        )}
      </div>
    </div>
  );
};
