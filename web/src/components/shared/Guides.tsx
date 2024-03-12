import { Heading } from '@/components/shared/Heading';
import { Button } from '@/components/ui/Button';

const guides = [
  {
    href: 'docs/getting-started/deploying-a-pipeline',
    name: '1. Deploy',
    description: () => (
      <span>
        Deploy a pipeline using the{' '}
        <Button href="#pipelines" disabled={true}>
          {' '}
          Create Pipeline
        </Button>{' '}
        button above.
      </span>
    ),
    readMoreText: 'Learn More',
  },
  {
    href: 'docs/getting-started/interacting-with-a-pipeline',
    name: '2. Interact',
    description: () => (
      <span>
        Interact with your deployment at {' '}
        <Button href="#pipelines" disabled={true}>
          {' sciphi-{...}-ue.a.run.app'}
          
        </Button>{'.'}
      </span>
    ),
    readMoreText: 'Learn More',
  },

  {
    href: 'docs/features/monitoring',
    name: '3. Monitor & Evaluate',
    description: 'Check for any logs & evaluate the quality of your RAG.',
    readMoreText: 'Learn More',
  },
  {
    href: 'docs/getting-started/rag-templates',
    name: '4. Customize',
    description: 'Create your own pipeline and deploy it from GitHub.',
    readMoreText: 'Learn More',
  },
];

export function Guides() {
  return (
    <div className="my-4 xl:max-w-none">
      <Heading level={2} id="guides" className="text-xl mb-4">
        Deploy your own rag pipeline
      </Heading>
      <div className="not-prose mt-4 grid grid-cols-1 gap-8 border-t border-zinc-900/5 pt-10 sm:grid-cols-2 xl:grid-cols-4 dark:border-white/5">
        {guides.map((guide) => (
          <div key={guide.href}>
            <h3 className="text-sm font-semibold text-zinc-900 dark:text-white">
              {guide.name}
            </h3>
            <p className="mt-1 text-sm text-zinc-600 dark:text-zinc-400">
              {typeof guide.description === 'function'
                ? guide.description()
                : guide.description}
            </p>
            <p className="mt-4">
              <Button href={guide.href} variant="text">
                {guide.readMoreText}
              </Button>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
