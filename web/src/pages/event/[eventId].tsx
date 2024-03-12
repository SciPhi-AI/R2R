import Link from 'next/link';
import { useRouter } from 'next/router';

import Layout from '@/components/Layout';
import { Separator } from '@/components/ui/separator';
import useLogs from '@/hooks/useLogs';
import styles from '@/styles/Index.module.scss';
import { EventSummary, searchResult } from '@/types';

function Component({ eventLog }: { eventLog: EventSummary }) {
  console.log('eventLog = ', eventLog);
  return (
    <div className="grid gap-6 lg:gap-8">
      <div className="space-y-4">
        {eventLog.searchQuery !== '' && (
          <div>
            <h2 className="pt-2 pb-2 text-lg font-semibold tracking-tight">
              Query
            </h2>
            <div className="pt-2 rounded-lg border p-4 bg-gray-50 dark:bg-gray-800">
              <span className="text-sm font-semibold text-gray-500 select-all sm:text-base/none dark:text-gray-200">
                {eventLog.searchQuery}
              </span>
            </div>
          </div>
        )}
        {eventLog.searchResults.length > 0 && (
          <div>
            <h2 className="text-lg pb-2 font-semibold tracking-tight">
              Search Results
            </h2>

            <div className="grid gap-4">
              {eventLog.searchResults.map(
                (result: searchResult, index: number) => (
                  <div
                    key={index}
                    className="border rounded-lg p-4 bg-gray-50 dark:bg-gray-800"
                  >
                    <div className="space-y-1">
                      <h3 className="text-base font-semibold tracking-tight">
                        {result.text.split('\\n')[0]}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {result.text.split('\\n').slice(1).join('\n')}
                      </p>
                    </div>
                  </div>
                )
              )}
            </div>
          </div>
        )}
      </div>
      {eventLog.completionResult !== 'N/A' && (
        <div>
          <h2 className="text-lg font-semibold tracking-tight">
            Completion Output
          </h2>
          <div className="rounded-lg border p-4 bg-gray-50 dark:bg-gray-800">
            <span className="text-sm text-gray-500 select-all sm:text-base/none dark:text-gray-200">
              {/* You can access the completion of your RAG pipeline event queries here. */}
              {eventLog.completionResult}
            </span>
          </div>
        </div>
      )}
      {eventLog.document !== null && (
        <div>
          <h2 className="text-lg font-semibold tracking-tight">DocumentID</h2>
          <div className="rounded-lg border p-4 bg-gray-50 dark:bg-gray-800">
            <span className="text-sm text-gray-500 select-all sm:text-base/none dark:text-gray-200">
              {/* You can access the completion of your RAG pipeline event queries here. */}
              {eventLog.document.id}
            </span>
          </div>
          <h2 className="text-lg font-semibold tracking-tight pt-4">
            Document Text
          </h2>
          <div className="rounded-lg border p-4 bg-gray-50 dark:bg-gray-800">
            <span className="text-sm text-gray-500 select-all sm:text-base/none dark:text-gray-200">
              {/* You can access the completion of your RAG pipeline event queries here. */}
              {eventLog.document.text}
            </span>
          </div>

          <h2 className="text-lg font-semibold tracking-tight pt-4">
            Metadata
          </h2>
          <div className="rounded-lg border p-4 bg-gray-50 dark:bg-gray-800">
            <span className="text-sm text-gray-500 select-all sm:text-base/none dark:text-gray-200">
              {/* You can access the completion of your RAG pipeline event queries here. */}
              {JSON.stringify(eventLog.document.metadata, null, 2)}
            </span>
          </div>
        </div>
      )}
      {eventLog.embeddingChunks && (
        <div>
          <h2 className="text-lg font-semibold tracking-tight pt-4">Chunks</h2>
          <div className="rounded-lg border p-4 bg-gray-50 dark:bg-gray-800">
            <span className="text-sm text-gray-500 select-all sm:text-base/none dark:text-gray-200">
              {/* You can access the completion of your RAG pipeline event queries here. */}
              {eventLog.embeddingChunks}
            </span>
          </div>
        </div>
      )}

      <div>
        {/* <h2 className="text-lg font-semibold tracking-tight">
          Other Key Metrics
        </h2>
        <div className="grid gap-2 md:grid-cols-1">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Processing Time
            </span>
            <span className="text-sm font-medium">2.1s</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Accuracy
            </span>
            <span className="text-sm font-medium">98.4%</span>
          </div>
          <div className="flex items-center space-x-2">
            <span className="text-sm font-medium text-gray-500 dark:text-gray-400">
              Confidence Score
            </span>
            <span className="text-sm font-medium">92.8%</span>
          </div>
        </div> */}
      </div>
    </div>
  );
}

export default function EventPage() {
  const router = useRouter();
  // Find the log with the matching run_id
  const eventId = router.query.eventId;
  const { logs, loading, error } = useLogs();
  // console.log('logs = ', logs);
  const eventLog = logs.find((log) => log.pipelineRunId === eventId);
  // console.log('eventLog = ', eventLog);

  // router.query.eventId will be the event ID from the path
  // For example, if the path is /event/55d05627-a4aa-426f-a4fc-10b2596e9ec5, router.query.eventId will be '55d05627-a4aa-426f-a4fc-10b2596e9ec5'
  // console.log(router.query.eventId);

  return (
    <Layout>
      <main className={styles.main}>
        <h1 className="text-white text-2xl mb-4">
          <Link
            className="pt-1"
            href={
              eventLog?.method !== 'Embedding'
                ? '../retrievals'
                : '../embeddings'
            }
            legacyBehavior
          >
            <a>
              <svg
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                className="h-6 w-6 inline-block align-text-top mr-2"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 19l-7-7m0 0l7-7m-7 7h18"
                />
              </svg>
            </a>
          </Link>
          {eventLog?.method} Event
          <span className="pl-3" style={{ fontSize: '1rem', color: '#888' }}>
            {eventId}{' '}
          </span>{' '}
        </h1>
        <Separator />

        {eventLog && <Component eventLog={eventLog} />}
      </main>
    </Layout>
  );
}
