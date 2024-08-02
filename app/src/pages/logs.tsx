'use client';
import { Loader } from 'lucide-react';
import React, { useState, useEffect } from 'react';

import Layout from '@/components/Layout';
import LogTable from '@/components/ui/logtable';
import { useUserContext } from '@/context/UserContext';

const Logs: React.FC = () => {
  const [isLoading, setIsLoading] = useState(true);
  const [logs, setLogs] = useState<any[]>([]);
  const { getClient, pipeline } = useUserContext();

  function sleep(ms: number) {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  const fetchLogs = async () => {
    try {
      const client = await getClient();
      if (!client) {
        throw new Error('Failed to get authenticated client');
      }

      const data = await client.logs();
      setLogs(data.results || []);
    } catch (error) {
      console.error('Error fetching logs:', error);
    }
  };

  useEffect(() => {
    if (pipeline?.deploymentUrl) {
      fetchLogs();
      sleep(1000).then(() => setIsLoading(false));
    }
  }, [pipeline?.deploymentUrl]);

  return (
    <Layout pageTitle="Logs" includeFooter={false}>
      <main className="w-full flex flex-col min-h-screen container">
        <div className="absolute inset-0 bg-zinc-900 mt-[5rem] sm:mt-[5rem] ">
          <div className="mx-auto max-w-6xl mb-12 mt-4 absolute inset-4 md:inset-1">
            {isLoading && (
              <Loader className="mx-auto mt-20 animate-spin" size={64} />
            )}

            {!isLoading && logs != null && (
              <LogTable logs={Array.isArray(logs) ? logs : []} />
            )}
          </div>
        </div>
      </main>
    </Layout>
  );
};

export default Logs;
