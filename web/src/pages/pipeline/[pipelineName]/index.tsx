import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import Layout from '@/components/Layout';
import { useAuth } from '@/context/authProvider';
import { createClient } from '@/utils/supabase/component';
import { usePipelineContext } from '@/context/PipelineContext';
import { Github, Link } from 'lucide-react';
import { Button } from '@/components/ui/Button';

import {
  CardTitle,
  CardDescription,
  CardHeader,
  CardContent,
  CardFooter,
  Card,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

import { Separator } from '@/components/ui/separator';
import styles from '@/styles/Index.module.scss';

const PipelinePage = () => {
  const [pipelineToDelete, setPipelineToDelete] = useState('');
  const [deleteButtonDisabled, setDeleteButtonDisabled] = useState(true);

  const { cloudMode } = useAuth();
  const supabase = createClient();
  const { pipelines, updatePipelines } = usePipelineContext();
  const router = useRouter();
  const pipelineId: any = router.query.pipelineName;
  const pipeline = pipelines[pipelineId];

  console.log('pipeline = ', pipeline);

  const handleDeletePipeline = async () => {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const token = session?.access_token;

    if (token) {
      if (pipelineId) {
        setDeleteButtonDisabled(true);

        const response = await fetch(
          `${process.env.NEXT_PUBLIC_CLOUD_REMOTE_SERVER_URL}/delete_pipeline/${pipelineId}`,
          {
            method: 'DELETE',
            headers: new Headers({
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            }),
          }
        );

        if (response.ok) {
          // Remove the deleted pipeline from the local state
          updatePipelines(pipelineId, null);
          setPipelineToDelete('');
          router.push('/');
          // Show a success message or perform any other necessary actions
        } else {
          // Handle the error case
          console.error('Failed to delete pipeline');
        }
      } else {
        console.error('Pipeline not found');
      }
    }
  };

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(
      () => {
        // Optional: Show a success message or perform any other actions
      },
      (err) => {
        console.error('Failed to copy text: ', err);
      }
    );
  };

  useEffect(() => {
    const update = async () => {
      console.log('pipelineId = ', pipelineId);
      if (pipelineId) {
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
  }, [pipelineId]);

  if (!pipeline) {
    return (
      <Layout>
        <main className={styles.main}>
          <div>Loading pipeline...</div>
        </main>
      </Layout>
    );
  }
  return (
    <Layout>
      <main className={styles.main}>
        {pipeline && (
          <h1 className="text-white text-2xl mb-4">
            Pipeline{' '}
            <code className="font-mono text-gray-500"> id:{pipeline.id}</code>
          </h1>
        )}
        <Separator />
        <Card className="my-6 w-full max-w-lg">
          <CardHeader className="pb-0">
            <CardTitle className="text-xl">{pipeline.name}</CardTitle>
            <CardDescription>
              This is a deployment of an immutable snapshot of RAG pipeline at a
              specific point in time.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid gap-4">
              <div className="flex items-center gap-4">
                {pipeline.deployment && pipeline.deployment?.uri && (
                  <>
                    <div className="flex items-center gap-2 mt-2">
                      <Link width="20" height="20" />
                      <span className="font-semibold">
                        {pipeline.deployment?.uri}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <CopyIcon
                        className="w-4 h-4 cursor-pointer"
                        onClick={() => handleCopy(pipeline.deployment?.uri)}
                      />
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
                {pipeline.deployment && pipeline.deployment?.create_time && (
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

              {pipeline.deployment && pipeline.deployment?.update_time && (
                <>
                  <Separator className="h-px" />
                  <div className="grid gap-2">
                    <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                      {'Last updated: ' + pipeline.deployment?.update_time}
                    </div>
                  </div>
                </>
              )}
              {pipeline.deployment && pipeline.deployment?.error && (
                <>
                  <Separator className="h-px" />
                  <div className="grid gap-2">
                    <div
                      className="flex items-center gap-2 text-red-500 dark:text-red-400 "
                      style={{
                        display: 'inline-block', // Ensures the element respects the maxWidth
                        maxWidth: '100%', // Ensures the span does not exceed the width of its container
                        overflowWrap: 'break-word', // Allows words to break and wrap to the next line
                        wordBreak: 'break-all', // To ensure even continuous strings without spaces will break
                      }}
                    >
                      {'Error: ' + pipeline.deployment?.error}
                    </div>
                  </div>
                </>
              )}
            </div>
          </CardContent>
          <CardFooter>
            <div className="flex flex-col w-full gap-4">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  {pipeline.status == 'finished' && (
                    <CheckCircleIcon className={'w-4 h-4'} />
                  )}

                  <span
                    className={
                      'text-sm' +
                      (pipeline.status == 'failed' ? ' text-red-500' : '')
                    }
                  >
                    {'Status: ' + pipeline.status.toUpperCase()}
                  </span>
                </div>
              </div>
              <Separator className="h-px" />
              <Label className="pl-1">Delete</Label>
              <div className="flex items-center -mt-2">
                <Input
                  type="text"
                  value={pipelineToDelete}
                  onChange={(e) => {
                    setPipelineToDelete(e.target.value);
                    setDeleteButtonDisabled(e.target.value !== pipeline.name);
                  }}
                  placeholder={`Enter pipeline name '${pipeline.name}' to enable delete.`}
                  className="flex-grow"
                  style={{
                    outline: 'none', // Removes the default outline
                    boxShadow: '0 0 2px #719ECE', // Sets a subtle glow, adjust as needed
                  }}
                />
                <Button
                  variant={deleteButtonDisabled ? 'disabled' : 'danger'}
                  className="px-4 py-2 ml-2"
                  onClick={handleDeletePipeline}
                  disabled={deleteButtonDisabled}
                >
                  Delete
                </Button>
              </div>
            </div>
          </CardFooter>
        </Card>
      </main>
    </Layout>
  );
};

function GitHubIcon(props) {
  return <Github width="16" height="16" />;
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
