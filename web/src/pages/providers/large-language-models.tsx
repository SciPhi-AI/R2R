import React, { lazy, Suspense } from 'react';

import { IntegrationCard } from '@/components/Feature/IntegrationCard';
import Layout from '@/components/Layout';
import LocalProvidersMenu from '@/components/Feature/LocalProvidersMenu';
import { Separator } from '@/components/UI/separator';
import { useFetchProviders } from '@/hooks/useFetchProviders';
import { useModal } from '@/hooks/useModal';
const SecretsModal = lazy(() => import('@/components/Feature/SecretsModal'));

import styles from '@/styles/Index.module.scss';

export default function LLMs() {
  const { isOpen, toggleModal, secretProvider, handleSecretProvider } =
    useModal();

  const { allProviders } = useFetchProviders();

  return (
    <Layout>
      <main className={styles.main}>
        <LocalProvidersMenu />

        <Separator />

        <div className={`${styles.gridView} ${styles.column}`}>
          {Array.isArray(allProviders)
            ? allProviders
                ?.filter((x) => {
                  return x?.type == 'llm_provider';
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
          {/* <PanelHeader text="Add LLM Provider" /> */}
        </div>
      </main>
    </Layout>
  );
}
