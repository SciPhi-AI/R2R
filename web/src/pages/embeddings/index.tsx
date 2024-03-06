import React from 'react';

import { Embeddings as EmbeddingsDash } from '@/components/Embeddings';
import Layout from '@/components/Layout';
import { Separator } from '@/components/ui/separator';

import styles from '../../styles/Index.module.scss';

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
