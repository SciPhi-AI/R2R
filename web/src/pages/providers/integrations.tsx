import React, { useEffect, useState } from 'react';

import { IntegrationCard } from '@/components/IntegrationCard';
import Layout from '@/components/Layout';
// import { PanelHeader } from '@/components/PanelHeader';
import { Separator } from '@/components/ui/separator';

import styles from '@/styles/Index.module.scss';
import { Provider } from '../../types';

export default function Integrations() {
  const [vectorProviders, setVectorProvider] = useState<Provider[]>([]);

  useEffect(() => {
    fetch('/api/integrations')
      .then((res) => res.json())
      .then((json) => setVectorProvider(json));
  }, []);

  return (
    <Layout>
      <main className={styles.main}>
        <h1 className="text-white text-2xl mb-4"> Integrations </h1>
        <Separator />

        <div className={`${styles.gridView} ${styles.column}`}>
          {Array.isArray(vectorProviders)
            ? vectorProviders
                ?.filter((x) => {
                  return x?.type == 'integration';
                })
                .map((provider) => (
                  <IntegrationCard provider={provider} key={provider.id} />
                ))
            : null}
        </div>
        <div className={styles.datasetHeaderRightAlign}>
          {/* <PanelHeader text="Add Integration" /> */}
        </div>
      </main>
    </Layout>
  );
}
