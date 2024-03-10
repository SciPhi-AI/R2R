import type { NextPage } from 'next';
import { useEffect, useState, useRef } from 'react';
import { createClient } from '@/utils/supabase/component';

import { Footer } from '@/components/Footer';
import Layout from '@/components/Layout';
import PipelineCard from '@/components/PipelineCard';
import { CreatePipelineHeader } from '@/components/CreatePipelineHeader';
import { Separator } from '@/components/ui/separator';
import Next from 'next/link';

import styles from '@/styles/Index.module.scss';
import 'react-tippy/dist/tippy.css';

import { Pipeline } from '@/types';
import { ContactResource } from '@/components/PipeCard';

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
      <main className={`${styles.main}`}>
        <h1 className="text-white text-2xl mb-4"> Pipelines </h1>
        <Separator />
        <div className="mt-6" />
        {error && <div className="text-red-500">{error}</div>}
        {isLoading ? (
          <div>Loading pipelines...</div>
        ) : (
          <>
            <CreatePipelineHeader numPipelines={pipelines?.length || 0} />
            <div className="not-prose mt-4 grid grid-cols-1 gap-8 border-t border-zinc-900/5 pt-10 sm:grid-cols-2 xl:grid-cols-4 dark:border-white/5">
              {/* <div className={styles.gridView}> */}
              {pipelines.map((pipeline) => (
                <ContactResource key={pipeline.id} pipeline={pipeline} />
              ))}
            </div>
          </>
        )}
        <br />
        <h1 className="text-white text-2xl mb-4"> Quickstart </h1>
        <Separator />
        <div className="mt-6 text-lg text-gray-200">
          <p>Follow these steps to deploy your R2R rag pipeline:</p>
          <ol className="list-decimal ml-4 pl-4 text-gray-300">
            <li> Deploy a pipeline using the `New Pipeline` button above.</li>
            <li>
              Monitor the deployment process and check for any logs or errors.
            </li>
            <li>
              Upon completion, your RAG application will be actively hosted at
              `https://sciphi-...-ue.a.run.app`.
            </li>
            <li>
              Customize - Use the R2R framework to create your own pipeline and
              deploy it directly from GitHub.
            </li>
          </ol>
          <p className="mt-2">
            For a detailed starting example, refer to the{' '}
            <Next
              href="https://github.com/SciPhi-AI/R2R-basic-rag-template"
              className="text-blue-500 hover:underline"
            >
              R2R-basic-rag-template documentation
            </Next>
            .
          </p>
        </div>
        <br />
      </main>
    </Layout>
  );
};

export default Home;
