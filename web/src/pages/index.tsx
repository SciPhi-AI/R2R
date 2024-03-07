import type { NextPage } from 'next';
import { useRouter } from 'next/router';
import { useEffect, useState, useRef } from 'react';
import { createClient } from '@/utils/supabase/component';

import { Footer } from '@/components/Footer';
import Layout from '@/components/Layout';
import { Card } from '@/components/PipelineCard';
import { CreatePipelineHeader } from '@/components/CreatePipelineHeader';
import { Separator } from '@/components/ui/separator';

import styles from '../styles/Index.module.scss';
import 'react-tippy/dist/tippy.css';

import { Pipeline } from '../types';

const Home: NextPage = () => {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const supabase = createClient();
  const pipelinesRef = useRef(pipelines);

  const fetchPipelines = () => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      const token = session?.access_token;
      if (token) {
        console.log("fetching....");
        fetch('/api/pipelines', {
          headers: new Headers({
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }),
        })
        .then((res) => res.json())
        .then((json) => {
          setPipelines(json['pipelines']);
        });
      }
    });
  };


  useEffect(() => {
    pipelinesRef.current = pipelines;
  }, [pipelines]);
  
  useEffect(() => {
    fetchPipelines();
    const interval = setInterval(() => {
      // Use the current value of the pipelines ref
      if (pipelinesRef.current.some(pipeline => ['building', 'pending', 'deploying'].includes(pipeline.status))) {
        fetchPipelines();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);


  return (
    <Layout>
      <main className={styles.main}>
        <h1 className="text-white text-2xl mb-4"> Pipelines </h1>
        <Separator />
        <div className="mt-6" />
        <CreatePipelineHeader numPipelines={pipelines?.length || 0} />

        <div className={styles.gridView}>
          {Array.isArray(pipelines)
            ? pipelines?.map((pipeline) => (
                <Card pipeline={pipeline} key={pipeline.id} />
              ))
            : null}
        </div>
        <br/>
      </main>
      <Footer />
    </Layout>
  );
};

export default Home;
