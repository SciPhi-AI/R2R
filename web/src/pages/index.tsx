import type { NextPage } from 'next';
import { useEffect, useState, useRef } from 'react';
import { createClient } from '@/utils/supabase/component';

import Layout from '@/components/Layout';
import { CreatePipelineHeader } from '@/components/CreatePipelineHeader';
import { Separator } from '@/components/ui/separator';
import Next from 'next/link';
import { Heading } from '@/components/shared/Heading';
import { Guides } from '@/components/shared/Guides';

import styles from '@/styles/Index.module.scss';
import 'react-tippy/dist/tippy.css';

import { Pipeline } from '@/types';
import { PipeCard } from '@/components/PipelineCard';

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
            <div className="not-prose mt-4 grid grid-cols-1 gap-8 border-t border-zinc-900/5 pt-10 sm:grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5 dark:border-white/5">
              {pipelines.map((pipeline) => (
                <PipeCard
                  key={pipeline.id}
                  pipeline={pipeline}
                  className="min-w-[200px] max-w-[300px]"
                />
              ))}
            </div>
          </>
        )}
        <br />
        <h1 className="text-white text-2xl mb-4"> Quickstart </h1>
        <Separator />
        <Guides />
      </main>
    </Layout>
  );
};

export default Home;
