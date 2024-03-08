import React, { useEffect, useState, lazy, Suspense } from 'react';

const SecretsModal = lazy(() => import('@/components/SecretsModal'));

import { IntegrationCard } from '@/components/IntegrationCard';
import Layout from '@/components/Layout';
import ProvidersNavMenu from '@/components/ProvidersNavMenu';
import { Separator } from '@/components/ui/separator';
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

import { useFetchProviders } from '@/hooks/useFetchProviders';

import { useModal } from '@/hooks/useModal';

import { Provider } from '@/types';

import styles from '@/styles/Index.module.scss';

// Assuming the data array is imported or defined somewhere in this file
const data = [
  {
    id: 'f1',
    dataset: 'teknium/OpenHermes-2.5',
    size: '1.94 GB',
    num_docs: '1.6 M',
    num_tokens: '110 M',
    status: 'available',
    provider: 'Provider A', // Example provider
  },
  {
    id: 'f2',
    dataset: 'math-ai/StackMathQA',
    size: '5.47 GB',
    num_docs: '6.19 M',
    num_tokens: '510 M',
    // status: "available",
    provider: 'HuggingFace',
  },
  {
    id: 'f3',
    dataset: 'Locutusque/UltraTextbooks',
    size: '22.3 GB',
    num_docs: '5.53 M',
    num_tokens: '2.34 B',
    // status: "available",
    provider: 'HuggingFace',
  },
  {
    id: 'f4',
    dataset: 'argilla/dpo-mix-7k',
    size: '78.2 M',
    num_docs: '7.5 K',
    num_tokens: '10 M',
    // status: "available",
    provider: 'HuggingFace',
  },
  {
    id: 'f5',
    dataset: 'imdb',
    size: '83.4 M',
    num_docs: '100 K',
    num_tokens: '10 M',
    // status: "uploading",
    provider: 'HuggingFace',
  },
];

export default function Datasets() {
  const { isOpen, toggleModal, secretProvider, handleSecretProvider } =
    useModal();
  const [integrationProviders, setIntegrationProvider] = useState<Provider[]>(
    []
  );

  const { allProviders } = useFetchProviders();

  return (
    <Layout>
      <main className={styles.main}>
        <ProvidersNavMenu />
        <Separator />

        <div className={`${styles.gridView} ${styles.column}`}>
          {Array.isArray(allProviders)
            ? allProviders
                ?.filter((x) => {
                  return x?.type == 'dataset-provider';
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
          {/* <PanelHeader text="Add Dataset Provider" /> */}
        </div>

        <div className="w-full">
          <Table className={styles.fullWidthTable}>
            {/* <TableCaption>A list of your recent invoices.</TableCaption> */}
            <TableHeader>
              <TableRow>
                <TableHead className="w-[100px]">Dataset</TableHead>
                <TableHead>Provider</TableHead>
                <TableHead>Size</TableHead>
                <TableHead className="text-right">Num Docs</TableHead>
                <TableHead className="text-right">Num Tokens</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((entry) => (
                <TableRow key={entry.dataset}>
                  <TableCell className="font-medium">{entry.dataset}</TableCell>
                  <TableCell>{entry.provider}</TableCell>
                  <TableCell>{entry.size}</TableCell>
                  <TableCell className="text-right">{entry.num_docs}</TableCell>
                  <TableCell className="text-right">
                    {entry.num_tokens}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
            <TableFooter>
              <TableRow>
                <TableCell colSpan={2}>Total</TableCell>
                <TableCell className="text-right">X</TableCell>
                <TableCell className="text-right">Y</TableCell>
                <TableCell className="text-right">Z</TableCell>
              </TableRow>
            </TableFooter>
          </Table>
        </div>
      </main>
    </Layout>
  );
}
