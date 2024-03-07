import styles from './styles.module.scss';
import React from 'react';
import { useRouter } from 'next/router';
import { useAuth } from '@/context/authProvider';

export function CreatePipelineHeader({
  numPipelines,
}: {
  numPipelines: number;
}) {
  const router = useRouter();
  const { cloudMode } = useAuth();

  const createPipeline = async () => {
    if (cloudMode === 'cloud') {
      router.push('/deploy');
    } else {
      router.push('/local_deploy');
    }
  };

  return (
    <div className={styles.container}>
      <button className={styles.newProjectButton} onClick={createPipeline}>
        New Pipeline
      </button>
      <span
        style={{ fontWeight: 'bold', marginLeft: '5px', marginTop: '10px' }}
      >
        {numPipelines}/10 pipelines deployed
      </span>
    </div>
  );
}
