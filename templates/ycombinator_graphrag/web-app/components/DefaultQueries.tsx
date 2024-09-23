import { Lightbulb, FlaskConical, Flame, Earth } from 'lucide-react';
import { FC } from 'react';

import { Logo } from '@/components/Logo';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface DefaultQueriesProps {
  setQuery: (query: string) => void;
}

export const DefaultQueries: FC<DefaultQueriesProps> = ({ setQuery }) => {
  const defaultQueries = [
    {
      query: 'What common themes emerged in this YC batch?',
      icon: <Lightbulb className="h-6 w-6 text-yellow-400" />,
    },
    {
      query: 'What is "Decisional AI" and who is similar to them?',
      icon: <FlaskConical className="h-6 w-6 text-purple-400" />,
    },
    {
      query: 'List as many healthcare startups as you can.',
      icon: <Flame className="h-6 w-6 text-red-400" />,
    },
    {
      query: "Which startups are likely to use LinkedIn heavily?",
      icon: <Earth className="h-6 w-6 text-green-400" />,
    },
  ];

  return (
    <div className="flex flex-col items-center justify-center h-full space-y-8">
      <Logo width={200} height={200} disableLink={true} />
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 w-full max-w-6xl px-4">
        {defaultQueries.map(({ query, icon }, index) => (
          <Alert
            key={index}
            className={`cursor-pointer hover:bg-zinc-200 flex flex-col items-start p-3 h-[100px] ${
              index >= 2 ? 'hidden sm:flex' : ''
            }`}
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
