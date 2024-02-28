import React, { useEffect, useState, lazy, Suspense } from 'react';

import { useProviderDataContext } from '@/context/providerContext'; // Import the context hook
import { IntegrationCard } from '@/components/IntegrationCard';
import Layout from '@/components/Layout';
import { Separator } from '@/components/ui/separator';
import LocalProvidersMenu from '@/components/LocalProvidersMenu';
import { useModal } from '@/hooks/useModal';

import styles from '@/styles/Index.module.scss';

const SecretsModal = lazy(() => import('@/components/SecretsModal'));

export default function LLMs() {
  const { isOpen, toggleModal, secretProvider, handleSecretProvider } =
    useModal();
  const { getFilteredProviders } = useProviderDataContext();

  const llmProviders = getFilteredProviders('llm_provider');

  useEffect(() => {
    console.log('LLM Providers:', llmProviders);
  }, [llmProviders]);

  return (
    <Layout>
      <main className={styles.main}>
        <LocalProvidersMenu />

        <Separator />

        <div className={`${styles.gridView} ${styles.column}`}>
          {Array.isArray(llmProviders)
            ? llmProviders.map((provider) => (
                <IntegrationCard
                  provider={provider}
                  key={provider.id}
                  onClick={() => handleSecretProvider(provider)}
                />
              ))
            : null}
        </div>
        <Suspense fallback={<div>Loading...</div>}>
          {isOpen && secretProvider && (
            <SecretsModal
              isOpen={isOpen}
              toggleModal={toggleModal}
              provider={secretProvider}
            />
          )}
        </Suspense>
        <div className={styles.datasetHeaderRightAlign}>
          {/* <PanelHeader text="Add LLM Provider" /> */}
        </div>
      </main>
    </Layout>
  );
}
