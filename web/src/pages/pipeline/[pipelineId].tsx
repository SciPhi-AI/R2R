import { useRouter } from 'next/router';
import { useEffect } from 'react';
import Layout from '@/components/Layout';
import { Footer } from '@/components/Footer';
import { useAuth } from '@/context/authProvider';
import { createClient } from '@/utils/supabase/component';
import { usePipelineContext } from '@/context/PipelineContext';
import { Github } from 'lucide-react';
import {
  CardTitle,
  CardDescription,
  CardHeader,
  CardContent,
  CardFooter,
  Card,
} from '@/components/ui/card';

import { Separator } from '@/components/ui/separator';
import styles from '../../styles/Index.module.scss';

const PipelinePage = () => {
  const { cloudMode } = useAuth();
  const supabase = createClient();
  const { pipelines, updatePipelines } = usePipelineContext();
  const router = useRouter();
  const pipelineId: any = router.query.pipelineId;
  const pipeline = pipelines[pipelineId]

  useEffect(() => {
    const update = async () => {
      if (cloudMode === 'cloud' && pipelineId) {
        // Use optional chaining
        const {
          data: { session },
        } = await supabase.auth.getSession();
        const token = session?.access_token;
        if (token) {
          // TODO - fetch the pipeline directly from the API
          const response = await fetch(`/api/pipelines`, {
            headers: new Headers({
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            }),
          });
          const data = await response.json();
          for (const pipeline of data.pipelines) {
            updatePipelines(pipeline.id, pipeline);
          }
        }
      }
    };

    update();
  }, [cloudMode, pipelineId]);

  if (!pipeline) {
    // Handle the case where pipeline is null or render nothing or a loader
    return <div>Loading...</div>; // or any other fallback UI
  }
  return (
    <Layout>
      <main className={styles.main}>
        {pipeline && (
          <h1 className="text-white text-2xl mb-4">
            {pipeline.name} Pipeline:{' '}
            <code className="font-mono text-gray-500">{pipeline.id}</code>
          </h1>
        )}
        <Separator />
        <Card className="my-6 w-full max-w-lg">
          <CardHeader className="pb-0">
            <CardTitle className="text-xl">Deployment</CardTitle>
            <CardDescription>
              Deployments are immutable snapshots of RAG pipeline at a specific
              point in time.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid gap-4">
              <div className="flex items-center gap-4">
                {pipeline.deployment && (
                  <>
                    <div className="flex items-center gap-2">
                      <GlobeIcon className="w-4 h-4" />
                      <span className="font-semibold">
                        {pipeline.deployment?.uri}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CopyIcon className="w-4 h-4" />
                    </div>
                </>
                )}
              </div>
              <div className="grid gap-2">
                <div className="flex items-center gap-2">
                  <GitHubIcon className="w-4 h-4" />
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    {pipeline.github_url}
                  </span>
                </div>
                {pipeline.deployment && (
                  <div className="flex items-center gap-2">
                    <CalendarClockIcon className="w-4 h-4" />
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {pipeline.deployment?.create_time}
                    </span>
                  </div>
                )}
                {/* <div className="flex items-center gap-2">
                  <UserIcon className="w-4 h-4" />
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    By shadcn
                  </span>
                </div> */}
              </div>
              {/* <Separator className="h-px" /> */}
              {/* <div className="grid gap-2">
                <div className="flex items-center gap-2">
                  <GitBranchIcon className="w-4 h-4" />
                  <span className="line-clamp-1">main</span>
                </div>
                <div className="flex items-center gap-2">
                  <GitCommitIcon className="w-4 h-4" />
                  <span className="line-clamp-1">
                    fix: auth issues for third-party integration
                  </span>
                </div>
              </div> */}
            {
              pipeline.deployment && 
              <>
                <Separator className="h-px" />
                <div className="grid gap-2">
                  <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                    {'Last updated: ' + pipeline.deployment?.update_time}
                  </div>
                </div>
              </>
          }
          </div>
          </CardContent>
          <CardFooter>
            <div className="flex w-full justify-between items-center gap-4">
              <div className="flex items-center gap-2">
                {pipeline.status == 'finished' && <CheckCircleIcon className="w-4 h-4" />}
                {pipeline.status}
              </div>
              {/* <Link
                className="flex items-center underline text-sm font-medium"
                href="#"
              >
                View Deployment
                <ChevronRightIcon className="w-4 h-4 ml-2 shrink-0" />
              </Link> */}
            </div>
          </CardFooter>
        </Card>
      </main>

      <Footer />
    </Layout>
  );
};

function GitHubIcon(props) {
  return (
    <Github width="16" height="16" />
  );
}

function GlobeIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="2" x2="22" y1="12" y2="12" />
      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
    </svg>
  );
}

function CopyIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect width="14" height="14" x="8" y="8" rx="2" ry="2" />
      <path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2" />
    </svg>
  );
}

function CalendarClockIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 7.5V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3.5" />
      <path d="M16 2v4" />
      <path d="M8 2v4" />
      <path d="M3 10h5" />
      <path d="M17.5 17.5 16 16.25V14" />
      <path d="M22 16a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z" />
    </svg>
  );
}

function UserIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" />
      <circle cx="12" cy="7" r="4" />
    </svg>
  );
}

function GitBranchIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="6" x2="6" y1="3" y2="15" />
      <circle cx="18" cy="6" r="3" />
      <circle cx="6" cy="18" r="3" />
      <path d="M18 9a9 9 0 0 1-9 9" />
    </svg>
  );
}

function GitCommitIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="3" />
      <line x1="3" x2="9" y1="12" y2="12" />
      <line x1="15" x2="21" y1="12" y2="12" />
    </svg>
  );
}

function CheckCircleIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

function ChevronRightIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="m9 18 6-6-6-6" />
    </svg>
  );
}
export default PipelinePage;
