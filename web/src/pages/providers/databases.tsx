import React, { useEffect, useState, lazy, Suspense } from 'react';

import { useModal } from '@/hooks/useModal';
const SecretsModal = lazy(() => import('@/components/SecretsModal'));

import Layout from '@/components/Layout';
import LocalProvidersMenu from '@/components/LocalProvidersMenu';

import { IntegrationCard } from '@/components/IntegrationCard';
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

export default function Databases({ active, others }) {
  const [databaseProviders, setDatabaseProviders] = useState<Provider[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<Provider | null>(
    null
  );
  const { isOpen, toggleModal } = useModal();

  useEffect(() => {
    fetch('/api/integrations')
      .then((res) => res.json())
      .then((json) => setDatabaseProviders(json));
  }, []);

  const renderProviders = () => {
    return databaseProviders
      .filter((provider) => provider?.type === 'vector-db-provider')
      .map((provider) => (
        <IntegrationCard
          provider={provider}
          key={provider.id}
          onClick={() => {
            setSelectedProvider(provider); // Set the selected provider
            toggleModal();
          }}
        />
      ));
  };

  return (
    <Layout>
      <main className={styles.main}>
        <LocalProvidersMenu />
        <Separator />
        <div className={`${styles.gridView} ${styles.column}`}>
          {Array.isArray(databaseProviders) ? renderProviders() : null}
        </div>
        <Suspense fallback={<div>Loading...</div>}>
          {isOpen && selectedProvider && (
            <SecretsModal
              isOpen={isOpen}
              toggleModal={() => {
                setSelectedProvider(null);
                toggleModal();
              }}
              provider={selectedProvider}
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
