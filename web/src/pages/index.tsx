// External Libraries
import { NextPage } from 'next';
import { useEffect, useState } from 'react';

// Utilities
import { createClient } from '@/utils/supabase/component';
import { useAuth } from '@/context/authProvider';

// Components
import Layout from '@/components/Layout';
import { Footer } from '@/components/Layout/Footer';
import { PipelineCard } from '@/components/Feature/PipelineCard';
import { CreatePipelineHeader } from '@/components/Feature/CreatePipelineHeader';
import { Separator } from '@/components/UI/separator';

// Types & Styles
import { Pipeline } from '@/types';
import styles from '@/styles/Index.module.scss';
import 'react-tippy/dist/tippy.css';

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
            .then((json) => setPipelines(json['pipelines']));
        }
      });
    }
  }, [cloudMode]);

  const handleAddPipeline = (newPipeline) => {
    setPipelines((prevPipelines) => [...prevPipelines, newPipeline]);
  };

  return (
    <Layout>
      <main className={styles.main}>
        <h1 className="text-white text-2xl mb-4">Pipelines</h1>
        <Separator />
        <div className="mt-6" />
        <CreatePipelineHeader onAddPipeline={handleAddPipeline} />
        <div className={styles.gridView}>
          {pipelines.map((pipeline) => (
            <PipelineCard key={pipeline.name} id={pipeline.id} />
          ))}
        </div>
      </main>
      <Footer />
    </Layout>
  );
};

export default Home;
