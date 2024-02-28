import React, { useEffect, useState, lazy, Suspense } from 'react';

import { useModal } from '@/hooks/useModal';
import { useProviderDataContext } from '@/context/providerContext'; // Import the context hook
import { IntegrationCard } from '@/components/IntegrationCard';

const SecretsModal = lazy(() => import('@/components/SecretsModal'));

import Layout from '@/components/Layout';
import LocalProvidersMenu from '@/components/LocalProvidersMenu';

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

import styles from '@/styles/Index.module.scss';
import { Provider } from '../../types';

// Assuming the data array is imported or defined somewhere in this file
const data = [
  {
    id: 'f1',
    provider: 'https://cloud.qdrant.io',
    collection: 'qdrant_0',
    size: '102.94 GB',
    num_vecs: '170.2 M',
    dimension: 768,
    status: 'available',
  },
  {
    id: 'f2',
    provider: 'https://www.trychroma.com/',
    collection: 'chroma_0',
    size: '130.94 GB',
    num_vecs: '230.2 M',
    dimension: 768,
  },
];

export default function Databases() {
  const { isOpen, toggleModal, secretProvider, handleSecretProvider } =
    useModal();
  const { getAllProviders, getFilteredProviders, getSelectedProvider } =
    useProviderDataContext();

  const providersArray = getAllProviders();
  const dataBaseProvidersArray = getFilteredProviders('vector-db-provider');

  // Log the database the providers
  useEffect(() => {
    console.log('Database Providers:', dataBaseProvidersArray);
  }, [providersArray]);

  // Log the data array
  // console.log('Data array:', data);

  return (
    <Layout>
      <main className={styles.main}>
        <LocalProvidersMenu />
        <Separator />
        <div className={`${styles.gridView} ${styles.column}`}>
          {Array.isArray(dataBaseProvidersArray)
            ? dataBaseProvidersArray.map((provider) => (
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
          {/* <PanelHeader text="Add VectorDB Provider" /> */}
        </div>

        <div className="w-full">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Provider</TableHead>
                <TableHead>Collection</TableHead>
                <TableHead>Size</TableHead>
                <TableHead className="text-right">Num Vecs</TableHead>
                <TableHead className="text-right">Dimension</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell>{entry.provider}</TableCell>
                  <TableCell>{entry.collection}</TableCell>
                  <TableCell>{entry.size}</TableCell>
                  <TableCell className="text-right">{entry.num_vecs}</TableCell>
                  <TableCell className="text-right">
                    {entry.dimension}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
            <TableFooter></TableFooter>
          </Table>
        </div>
      </main>
    </Layout>
  );
}
