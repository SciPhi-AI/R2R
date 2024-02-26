import React from 'react';

import { Event as EventDash } from '@/components/Events';
import Layout from '@/components/Layout';
import { Separator } from '@/components/ui/separator';

import styles from '../../styles/Index.module.scss';

export default function Events() {
  return (
    <Layout>
      <main className={styles.main}>
        <h1 className="text-white text-2xl mb-4"> Events </h1>
        <Separator />
        <EventDash />
      </main>
    </Layout>
  );
}
