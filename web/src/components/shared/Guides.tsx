import { Heading } from '@/components/shared/Heading';
import { Button } from '@/components/ui/Button';

const guides = [
  {
    href: '#',
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
    readMoreText: 'Read More',
    readMoreHref: '#deployDetails',
  },
  {
    href: '#',
    name: '2. Monitor',
    description: 'Check for any logs or errors in the deployment process',
    readMoreText: 'Monitoring Tips',
  },
  {
    href: '#',
    name: '3. Host',
    description:
      'Upon completion, your RAG application will be actively hosted at',
    readMoreText: 'sciphi-{...}-ue.a.run.app',
  },
  {
    href: 'https://github.com/SciPhi-AI/R2R',
    name: '4. Customize',
    description: 'Create your own pipeline and deploy it from GitHub.',
    readMoreText: 'Use R2R framework',
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
