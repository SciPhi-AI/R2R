import React, { useEffect, useState } from 'react';

//import { IntegrationCard } from '@/components/IntegrationCard';
import Layout from '@/components/Layout';
//import { PanelHeader } from '@/components/PanelHeader';
import { Separator } from '@/components/UI/separator';

import styles from '../styles/Index.module.scss';
import { Pipeline } from '../types';

export default function Settings() {
  const [vectorProviders, setVectorProvider] = useState<Pipeline[]>([]);

  useEffect(() => {
    fetch('/api/integrations')
      .then((res) => res.json())
      .then((json) => setVectorProvider(json));
  }, []);

  return (
    <Layout>
      <main className={styles.main}>
        <h1 className="text-white text-2xl mb-4"> Settings </h1>
        <Separator />
      </main>
    </Layout>
  );
}
