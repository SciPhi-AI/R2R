import React from 'react';

import { Retrieval as RetrievalDash } from '@/components/Retrievals';
import Layout from '@/components/Layout';
import { Separator } from '@/components/ui/separator';

import styles from '../../styles/Index.module.scss';

export default function Retrievals() {
  return (
    <Layout>
      <main className={styles.main}>
        <h1 className="text-white text-2xl mb-4"> Retrievals </h1>
        <Separator />
        <RetrievalDash />
      </main>
    </Layout>
  );
}
