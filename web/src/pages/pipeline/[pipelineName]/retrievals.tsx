import { useRouter } from 'next/router';
import { useEffect } from 'react';
import React from 'react';

import Layout from '@/components/Layout';
import { Retrieval as RetrievalDash } from '@/components/retrievals';
import { Separator } from '@/components/ui/separator';
import { usePipelineContext } from '@/context/PipelineContext';
import styles from '@/styles/Index.module.scss';
import { createClient } from '@/utils/supabase/component';

export default function Retrievals() {
  const router = useRouter();
  const supabase = createClient();

  const { pipelines, updatePipelines } = usePipelineContext();
  const pipelineId: any = router.query.pipelineName;
  const pipeline = pipelines[pipelineId];

  useEffect(() => {
    try {
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
    } catch (error) {
      console.error('Error fetching pipeline:', error);
    }
  }, [pipelineId]);

  console.log('passing pipeline = ', pipeline);
  return (
    <Layout>
      <main className={styles.main}>
        <h1 className="text-white text-2xl mb-4"> Retrievals </h1>
        <Separator />
        <RetrievalDash pipeline={pipeline} />
      </main>
    </Layout>
  );
}
