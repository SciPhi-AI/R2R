import React, { useState, useEffect } from 'react';
import { FC } from 'react';
import Markdown from 'react-markdown';

import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ChatDemo/popover';
import { Skeleton } from '@/components/ChatDemo/skeleton';
import { Logo } from '@/components/shared/Logo';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Message } from '@/types';
import { Source } from '@/types';

const SourceItem: FC<{ source: Source }> = ({ source }) => {
  const { id, score, metadata } = source;

  return (
    <div className="bg-zinc-700 p-3 rounded-lg mb-2" style={{ width: '100%' }}>
      <h3 className="text-xs font-medium text-zinc-200 mb-1">
        {metadata.title} (Similarity: {score.toFixed(3)})
      </h3>
      <p className="text-xs text-zinc-400">{metadata.text}</p>
    </div>
  );
};

function formatMarkdownNewLines(markdown: string) {
  return markdown
    .replace(/\[(\d+)]/g, '[$1]($1)')
    .split(`"queries":`)[0]
    .replace(/\\u[\dA-F]{4}/gi, (match: string) => {
      return String.fromCharCode(parseInt(match.replace(/\\u/g, ''), 16));
    });
}

const parseSources = (sources: string | object): Source[] => {
  if (typeof sources === 'string') {
    // Split the string into individual JSON object strings
    const individualSources = sources.split(',"{"').map((source, index) => {
      if (index === 0) {
        return source;
      } // First element is already properly formatted
      return `{"${source}`; // Wrap the subsequent elements with leading `{"`
    });

    // Wrap the individual sources in a JSON array format
    const jsonArrayString = `[${individualSources.join(',')}]`;

    try {
      const partialParsedSources = JSON.parse(jsonArrayString);
      return partialParsedSources.map((source: any) => {
        return JSON.parse(source);
      });
    } catch (error) {
      console.error('Failed to parse sources:', error);
      throw new Error('Invalid sources format');
    }
  }

  return sources as Source[];
};

export const Answer: FC<{
  message: Message;
  isStreaming: boolean;
  isSearching: boolean;
  mode: 'rag' | 'rag_agent';
}> = ({ message, isStreaming, isSearching, mode }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [parsedSources, setParsedSources] = useState<Source[]>([]);

  useEffect(() => {
    if (message.sources) {
      try {
        const parsed = parseSources(message.sources);
        setParsedSources(parsed);
      } catch (error) {
        console.error('Failed to parse sources:', error);
        setParsedSources([]);
      }
    } else {
      setParsedSources([]);
    }
  }, [message.sources]);

  const showSourcesAccordion =
    mode === 'rag' || (mode === 'rag_agent' && parsedSources.length > 0);
  const showNoSourcesFound =
    mode === 'rag_agent' &&
    message.searchPerformed &&
    parsedSources.length === 0;

  return (
    <div className="mt-4">
      {showSourcesAccordion && (
        <Accordion
          type="single"
          collapsible
          className="w-full"
          onValueChange={(value) => setIsOpen(value === 'answer')}
        >
          <AccordionItem value="answer">
            <AccordionTrigger className="py-2 text-lg font-bold text-zinc-200 hover:no-underline">
              <div className="flex items-center justify-between w-full">
                <Logo width={25} disableLink={true} />
                <span className="text-sm font-normal">
                  {isSearching ? (
                    <span className="searching-animation">
                      Searching over sources...
                    </span>
                  ) : (
                    `View ${parsedSources.length} Sources`
                  )}
                </span>
              </div>
            </AccordionTrigger>
            <AccordionContent>
              <div className="space-y-2 pt-2">
                <div className="space-y-2 max-h-60 overflow-y-auto">
                  {parsedSources.map((item: Source) => (
                    <SourceItem key={item.id} source={item} />
                  ))}
                </div>
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      )}

      {showNoSourcesFound && (
        <div className="flex items-center justify-between py-2 text-sm text-zinc-400">
          <Logo width={25} disableLink={true} />
          <span>No sources found</span>
        </div>
      )}

      {mode === 'rag_agent' && !showSourcesAccordion && !showNoSourcesFound && (
        <div className="flex items-center py-2">
          <Logo width={25} disableLink={true} />
        </div>
      )}

      <div className="space-y-4 mt-4">
        {message.content ? (
          <div className="prose prose-sm max-w-full text-zinc-300 overflow-y-auto max-h-[700px] prose-headings:text-white prose-p:text-white prose-strong:text-white prose-code:text-white">
            <Markdown
              components={{
                h1: (props) => <h1 className="prose-heading" {...props} />,
                h2: (props) => <h2 className="prose-heading" {...props} />,
                h3: (props) => <h3 style={{ color: 'white' }} {...props} />,
                h4: (props) => <h4 style={{ color: 'white' }} {...props} />,
                h5: (props) => <h5 style={{ color: 'white' }} {...props} />,
                h6: (props) => <h6 style={{ color: 'white' }} {...props} />,
                strong: (props) => (
                  <strong
                    style={{ color: 'white', fontWeight: 'bold' }}
                    {...props}
                  />
                ),
                p: (props) => <p style={{ color: 'white' }} {...props} />,
                li: (props) => <li style={{ color: 'white' }} {...props} />,
                blockquote: (props) => (
                  <blockquote style={{ color: 'white' }} {...props} />
                ),
                em: (props) => <em style={{ color: 'white' }} {...props} />,
                code: (props) => <code style={{ color: 'white' }} {...props} />,
                pre: (props) => <pre style={{ color: 'white' }} {...props} />,
                a: ({ href, ...props }) => {
                  if (!href) return null;
                  const source = parsedSources[+href - 1];
                  if (!source) return null;
                  const metadata = source.metadata;
                  return (
                    <span className="inline-block w-4">
                      <Popover>
                        <PopoverTrigger asChild>
                          <span
                            title={metadata?.title}
                            className="inline-block cursor-pointer transform scale-[60%] no-underline font-medium bg-zinc-700 hover:bg-zinc-500 w-6 text-center h-6 rounded-full origin-top-left"
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
                                {metadata?.text ?? ''}
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
              {formatMarkdownNewLines(message.content)}
            </Markdown>
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
