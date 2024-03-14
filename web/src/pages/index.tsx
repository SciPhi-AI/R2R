import type { NextPage } from 'next';
import { getServerSession } from 'next-auth/next';
import { PostHog } from 'posthog-node';
import { useEffect, useState, useRef } from 'react';

import { CreatePipelineHeader } from '@/components/CreatePipelineHeader';
import Layout from '@/components/Layout';
import { PipeCard } from '@/components/PipelineCard';
import { Guides } from '@/components/shared/Guides';
import { Heading } from '@/components/shared/Heading';
import { Separator } from '@/components/ui/separator';
import styles from '@/styles/Index.module.scss';
import 'react-tippy/dist/tippy.css';
import { Pipeline } from '@/types';
import { createClient } from '@/utils/supabase/component';

const Home: NextPage = () => {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const supabase = createClient();
  const pipelinesRef = useRef(pipelines);
  const [currentUser, setCurrentUser] = useState(null);

  const fetchPipelines = () => {
    setError(null);
    supabase.auth.getSession().then(({ data: { session } }) => {
      const token = session?.access_token;
      if (token) {
        fetch('/api/pipelines', {
          headers: new Headers({
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          }),
        })
          .then((res) => {
            if (!res.ok) {
              throw new Error('Network response was not ok');
            }
            return res.json();
          })
          .then((json) => {
            console.log('setting pipelines = ', json['pipelines']);
            setPipelines(json['pipelines']);
          })
          .catch((error) => {
            setError('Failed to load pipelines');
            console.error('Error fetching pipelines:', error);
          })
          .finally(() => {
            setIsLoading(false);
          });
      } else {
        setError('Authentication token is missing');
        setIsLoading(false);
      }
    });
  };

  useEffect(() => {
    pipelinesRef.current = pipelines;
  }, [pipelines]);
  useEffect(() => {
    const fetchSession = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      setCurrentUser(session?.user || null);
      // Redirect if there is no user in the session
      if (!session?.user) {
        window.location.href = '/login';
      }
    };

    fetchSession();
  }, [supabase]);

  useEffect(() => {
    fetchPipelines();
    const interval = setInterval(() => {
      // Use the current value of the pipelines ref
      if (
        pipelinesRef?.current?.some((pipeline) =>
          ['building', 'pending', 'deploying'].includes(pipeline.status)
        )
      ) {
        if (pipelinesRef?.current.length === 0) {
          console.log('No pipelines found');
          setIsLoading(true);
        }

        fetchPipelines();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, [currentUser]);

  return (
    <Layout>
      <main className={styles.main}>
        <Heading id="pipelines" level={2} className="text-2xl mb-4">
          Pipelines{' '}
        </Heading>
        <Separator />
        <div className="mt-6" />
        {error && <div className="text-red-500">{error}</div>}
        {isLoading ? (
          <div>Loading pipelines...</div>
        ) : (
          <>
            <CreatePipelineHeader numPipelines={pipelines?.length || 0} />
            <div className="not-prose grid grid-cols-1 gap-10 pt-10 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 dark:border-white/5">
              {pipelines.map((pipeline) => (
                <PipeCard
                  key={pipeline.id}
                  pipeline={pipeline}
                  className="min-w-[250px] max-w-[300px]"
                />
              ))}
            </div>
          </>
        )}
        <br />
        <Separator />
        <h1 className="text-white text-2xl mt-4"> Quickstart: </h1>
        <Guides />
      </main>
    </Layout>
  );
};

export async function getServerSideProps(ctx) {
  const session = await getServerSession(ctx.req, ctx.res, {});
  let flags = null;

  if (session) {
    console.log('pinging posthog...');
    const client = new PostHog(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
      host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
    });

    flags = await client.getAllFlags(session.user.email);
    client.capture({
      distinctId: session.user.email,
      event: 'loaded blog article',
      properties: {
        $current_url: ctx.req.url,
      },
    });

    await client.shutdownAsync();
  }
  return { props: { session, flags } };
}

export default Home;
