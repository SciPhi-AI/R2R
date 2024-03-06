import type { NextPage } from 'next';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import { createClient } from '@/utils/supabase/component';
import { useUpdatePipelineProp } from '@/hooks/useUpdatePipelineProp';

import { Footer } from '@/components/Footer';
import Layout from '@/components/Layout';
import { PipelineCard } from '@/components/PipelineCard';
import { CreatePipelineHeader } from '@/components/CreatePipelineHeader';
import { Separator } from '@/components/ui/separator';

import styles from '../styles/Index.module.scss';
import 'react-tippy/dist/tippy.css';

import { Pipeline } from '../types';
import { useAuth } from '@/context/authProvider';

const Home: NextPage = () => {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const supabase = createClient();
  const { cloudMode } = useAuth();

  useEffect(() => {
    if (cloudMode === 'cloud') {
      supabase.auth.getSession().then(({ data: { session } }) => {
        const token = session?.access_token;
        if (token) {
          console.log('fetching from GitHub...');
          fetch('/api/pipelines', {
            headers: new Headers({
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            }),
          })
            .then((res) => res.json())
            .then((json) => {
              setPipelines(json['pipelines']);
            });
        }
      });
    }
  }, [cloudMode]);

  // useEffect(() => {
  //   router.push('/retrievals');
  // }, [router]);

  const handleAddPipeline = (newPipeline) => {
    setPipelines((prevPipelines) => [...prevPipelines, newPipeline]);
  };

  return (
    <Layout>
      <main className={styles.main}>
        <h1 className="text-white text-2xl mb-4"> Pipelines </h1>
        <Separator />
        <div className="mt-6" />
        <CreatePipelineHeader onAddPipeline={handleAddPipeline} />

        <div className={styles.gridView}>
          {Array.isArray(pipelines)
            ? pipelines.map((pipeline) => (
                <PipelineCard key={pipeline.name} id={pipeline.id} />
              ))
            : null}
        </div>
      </main>
      <Footer />
    </Layout>
  );
};

export default Home;
