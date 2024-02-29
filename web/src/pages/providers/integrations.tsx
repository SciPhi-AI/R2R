import React, { useEffect, useState, lazy, Suspense } from 'react';

import { IntegrationCard } from '@/components/IntegrationCard';
import Layout from '@/components/Layout';
// import { PanelHeader } from '@/components/PanelHeader';
import { Separator } from '@/components/ui/separator';
import LocalProvidersMenu from '@/components/LocalProvidersMenu';

import { useModal } from '@/hooks/useModal';

const SecretsModal = lazy(() => import('@/components/SecretsModal'));

import styles from '@/styles/Index.module.scss';
import { Provider } from '../../types';

export default function Integrations() {
  const { isOpen, toggleModal, secretProvider, handleSecretProvider } =
    useModal();
  const [integrationProviders, setIntegrationProvider] = useState<Provider[]>(
    []
  );

  useEffect(() => {
    fetch('/api/integrations')
      .then((res) => res.json())
      .then((json) => setIntegrationProvider(json));
  }, []);

  return (
    <Layout>
      <main className={styles.main}>
        <LocalProvidersMenu />
        <Separator />

        <div className={`${styles.gridView} ${styles.column}`}>
          {Array.isArray(integrationProviders)
            ? integrationProviders
                ?.filter((x) => {
                  return x?.type == 'integration';
                })
                .map((provider) => (
                  <IntegrationCard
                    provider={provider}
                    key={provider.id}
                    onClick={() => handleSecretProvider(provider)}
                  />
                ))
            : null}
          <Suspense fallback={<div>Loading...</div>}>
            {isOpen && secretProvider && (
              <SecretsModal
                isOpen={isOpen}
                toggleModal={toggleModal}
                provider={secretProvider}
              />
            )}
          </Suspense>
        </div>
        <div className={styles.datasetHeaderRightAlign}>
          {/* <PanelHeader text="Add Integration" /> */}
        </div>
      </main>
    </Layout>
  );
}
