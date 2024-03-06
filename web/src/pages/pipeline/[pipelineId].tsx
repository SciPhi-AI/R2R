// External Imports
import { useRouter } from 'next/router';
import { useEffect } from 'react';
import Link from 'next/link';

// Context & Hooks
import { useAuth } from '@/context/authProvider';
import { usePipelineContext } from '@/context/PipelineContext';
import { useUpdatePipelineProp } from '@/hooks/useUpdatePipelineProp';

// Utilities
import { createClient } from '@/utils/supabase/component';

// Components & Styles
import Layout from '@/components/Layout';
import { Footer } from '@/components/Layout/Footer';
import {
  Card,
  CardTitle,
  CardDescription,
  CardHeader,
  CardContent,
  CardFooter,
} from '@/components/UI/card';
import { Separator } from '@/components/UI/separator';
import {
  GlobeIcon,
  CopyIcon,
  CalendarClockIcon,
  UserIcon,
  GitBranchIcon,
  GitCommitIcon,
  CheckCircleIcon,
  ChevronRightIcon,
} from '@/components/icons'; // Assuming icons are moved
import styles from '../../styles/Index.module.scss';

// Types
import { Pipeline } from '@/types';

const PipelinePage = () => {
  const { cloudMode } = useAuth();
  const supabase = createClient();
  const updatePipelineProp = useUpdatePipelineProp();
  const { pipeline } = usePipelineContext();

  useEffect(() => {
    const fetchPipeline = async () => {
      if (cloudMode === 'cloud' && pipeline?.id) {
        const {
          data: { session },
        } = await supabase.auth.getSession();
        const token = session?.access_token;
        if (token) {
          const response = await fetch(`/api/pipelines/${pipeline.id}`, {
            headers: new Headers({
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            }),
          });
          const data = await response.json();
          if (data.pipeline) {
            Object.keys(data.pipeline).forEach((key) => {
              updatePipelineProp(key as keyof Pipeline, data.pipeline[key]);
            });
          }
        }
      }
    };

    fetchPipeline();
  }, [cloudMode, pipeline?.id, updatePipelineProp]);

  if (!pipeline) {
    return <div>Loading...</div>;
  }

  return (
    <Layout>
      <main className={styles.main}>
        <h1 className="text-white text-2xl mb-4">
          {pipeline.name} Pipeline:{' '}
          <code className="font-mono text-gray-500">{pipeline.id}</code>
        </h1>
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
                <div className="flex items-center gap-2">
                  <GlobeIcon className="w-4 h-4" />
                  <span className="font-semibold">
                    {pipeline.deployment_url}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <CopyIcon className="w-4 h-4" />
                </div>
              </div>
              <div className="grid gap-2">
                <div className="flex items-center gap-2">
                  <CalendarClockIcon className="w-4 h-4" />
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    Created 1m ago
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <UserIcon className="w-4 h-4" />
                  <span className="text-sm text-gray-500 dark:text-gray-400">
                    By shadcn
                  </span>
                </div>
              </div>
              <Separator className="h-px" />
              <div className="grid gap-2">
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
              </div>
              <Separator className="h-px" />
              <div className="grid gap-2">
                <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                  17m ago by owen
                </div>
              </div>
            </div>
          </CardContent>
          <CardFooter>
            <div className="flex w-full justify-between items-center gap-4">
              <div className="flex items-center gap-2">
                <CheckCircleIcon className="w-4 h-4" />
                Ready
              </div>
              <Link
                className="flex items-center underline text-sm font-medium"
                href="#"
              >
                View Deployment
                <ChevronRightIcon className="w-4 h-4 ml-2 shrink-0" />
              </Link>
            </div>
          </CardFooter>
        </Card>
      </main>

      <Footer />
    </Layout>
  );
};

export default PipelinePage;
