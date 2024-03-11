import { Button } from '@/components/Button';
import { Heading } from '@/components/Heading';
import Link from 'next/link';

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
    readMoreText: 'Learn More',
    readMoreHref: '#deployDetails',
  },
  {
    href: '#',
    name: 'Monitor',
    description: 'Check for any logs or errors in the deployment process',
    readMoreText: 'Monitoring Tips',
  },
  {
    href: 'https://sciphi-example-id-ue.a.run.app',
    name: 'Host',
    description:
      'Upon completion, your RAG application will be actively hosted at',
    readMoreText: 'Monitoring Tips',
    // Assuming this guide doesn't need a "Read more" button
  },
  {
    href: '$',
    name: 'Customize',
    description:
      'Use the R2R framework to create your own pipeline and deploy it directly from GitHub.',
    readMoreText: 'Customization Guide',
  },
];

export function Guides() {
  return (
    <div className="my-16 xl:max-w-none">
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
                Read more
              </Button>
            </p>
          </div>
        ))}
      </div>
    </div>
  );
}
