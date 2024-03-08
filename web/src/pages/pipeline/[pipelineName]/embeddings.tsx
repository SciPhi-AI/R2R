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
