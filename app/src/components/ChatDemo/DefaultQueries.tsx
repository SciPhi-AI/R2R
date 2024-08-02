import { Lightbulb, FlaskConical, Flame, Earth } from 'lucide-react';
import { FC } from 'react';

import { Logo } from '@/components/shared/Logo';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { DefaultQueriesProps } from '@/types';

export const DefaultQueries: FC<DefaultQueriesProps> = ({ setQuery, mode }) => {
  const defaultRagQueries = [
    {
      query: 'What is the main topic of the uploaded documents?',
      icon: <Lightbulb className="h-6 w-6 text-yellow-400" />,
    },
    {
      query: 'Summarize key points for me.',
      icon: <FlaskConical className="h-6 w-6 text-purple-400" />,
    },
    {
      query: 'What issues do you see with the documents?',
      icon: <Flame className="h-6 w-6 text-red-400" />,
    },
    {
      query: 'How are these documents interrelated?',
      icon: <Earth className="h-6 w-6 text-green-400" />,
    },
  ];

  const defaultAgentQueries = [
    {
      query: 'Hey! How are you today?',
      icon: <Lightbulb className="h-6 w-6 text-yellow-400" />,
    },
    {
      query: 'Can you help me understand my documents better?',
      icon: <FlaskConical className="h-6 w-6 text-purple-400" />,
    },
    {
      query: 'How might agentic RAG help me in the long run?',
      icon: <Flame className="h-6 w-6 text-red-400" />,
    },
    {
      query: 'What is the coolest thing you can do?',
      icon: <Earth className="h-6 w-6 text-green-400" />,
    },
  ];

  const getQueriesBasedOnMode = (mode: 'rag' | 'rag_agent') => {
    if (mode === 'rag') {
      return defaultRagQueries;
    } else if (mode === 'rag_agent') {
      return defaultAgentQueries;
    } else {
      throw new Error('Invalid mode');
    }
  };

  const defaultQueries = getQueriesBasedOnMode(mode);

  return (
    <div className="flex flex-col items-center justify-center h-full space-y-8">
      <Logo width={200} height={200} disableLink={true} />
      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 w-full max-w-4xl px-4">
        {defaultQueries.map(({ query, icon }, index) => (
          <Alert
            key={index}
            className="cursor-pointer hover:bg-zinc-700 flex flex-col items-start p-3 h-[100px]"
            onClick={() => setQuery(query)}
          >
            <div className="mb-2">{icon}</div>
            <AlertDescription className="text-sm text-left">
              {query}
            </AlertDescription>
          </Alert>
        ))}
      </div>
    </div>
  );
};
