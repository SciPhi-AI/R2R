import React from 'react';

// import pipelinecontext
import { useEffect } from 'react';
import { useRouter } from 'next/router';
import { usePipelineContext } from '@/context/PipelineContext';
import { AuthProvider, useAuth } from '@/context/authProvider';

import { Embeddings as EmbeddingsDash } from '@/components/Embeddings';
import Layout from '@/components/Layout';
import { Separator } from '@/components/ui/separator';
import { createClient } from '@/utils/supabase/component';

import styles from '@/styles/Index.module.scss';

export default function Embeddings() {
  const { pipelines, updatePipelines } = usePipelineContext();
  const { cloudMode } = useAuth();
  const supabase = createClient();

  const router = useRouter();
  const { pipelineName } = router.query;
  console.log('pipelineName = ', pipelineName);
  const pipeline = pipelines[pipelineName as string];
  const pipelineId = pipeline?.id?.toString();

  useEffect(() => {
    const update = async () => {
      try {
        const response = await fetch(`/api/local_pipelines`, {
          headers: new Headers({
            'Content-Type': 'application/json',
          }),
        });
        const data = await response.json();
        for (const pipeline of data.pipelines) {
          updatePipelines(pipeline.name, pipeline);
        }
      } catch (error) {
        console.error('Error updating local pipeline:', error);
      }
    };

    update();
  }, [pipelineName]);

  // useEffect(() => {
  //   const update = async () => {
  //     if (cloudMode === 'cloud' && pipelineId) {
  //       // Use optional chaining
  //       const {
  //         data: { session },
  //       } = await supabase.auth.getSession();
  //       const token = session?.access_token;
  //       if (token) {
  //         // TODO - fetch the pipeline directly from the API
  //         const response = await fetch(`/api/pipelines`, {
  //           headers: new Headers({
  //             Authorization: `Bearer ${token}`,
  //             'Content-Type': 'application/json',
  //           }),
  //         });
  //         const data = await response.json();
  //         for (const pipeline of data.pipelines) {
  //           updatePipelines(pipeline.id, pipeline);
  //         }
  //       }
  //     } else {
  //       try {
  //         const response = await fetch(`/api/local_pipelines`, {
  //           headers: new Headers({
  //             'Content-Type': 'application/json',
  //           }),
  //         });
  //         const data = await response.json();
  //         for (const pipeline of data.pipelines) {
  //           updatePipelines(pipeline.name, pipeline);
  //         }
  //       } catch (error) {
  //         console.error('Error updating local pipeline:', error);
  //       }
  //     }
  //   };

  //   update();
  // }, [cloudMode, pipelineId]);

  console.log('pipeline = ', pipeline);
  if (pipeline) {
    console.log('pipelineId = ', pipeline.id);
    console.log('pipelineName= ', pipeline.name);
  } else {
    console.log('Pipeline data is not available');
  }

  if (!pipeline) {
    // Handle the case where pipeline is null or render nothing or a loader
    return <div>Loading...</div>; // or any other fallback UI
  }
  return (
    <Layout>
      <main className={styles.main}>
        <h1 className="text-white text-2xl mb-4"> Embeddings </h1>
        <Separator />
        <EmbeddingsDash />
      </main>
    </Layout>
  );
}
