import { FiExternalLink } from 'react-icons/fi';
import { usePipelineContext } from '@/context/PipelineContext';
import { useRouter } from 'next/router';
import { useUpdatePipelineProp } from '@/hooks/useUpdatePipelineProp';
import React from 'react';

import styles from './styles.module.scss';
import { Pipeline } from '../../types';

interface PipelineCardProps {
  pipeline: Pipeline;
}

export default function PipelineCard({ pipeline }: PipelineCardProps) {
  const router = useRouter();

  const handleClick = () => {
    router.push(`/pipeline/${pipeline.id}`);
  };

  return (
    <a href="#" className={styles.container} onClick={handleClick}>
      <div className={styles.cardHeader}>
        <div className={styles.hoverRedirectIcon}>
          <FiExternalLink size="16" />
        </div>

        <div className={styles.projectInfo}>
          <p className={styles.cardTitle}>Pipeline:</p>
          <strong className={styles.cardProjectTitle}>{pipeline.name}</strong>
          {pipeline.status === 'finished' ? (
            <>
              <p className={styles.cardTitle}>Remote:</p>
              <p className={styles.cardAddress}>{pipeline.github_url}</p>

              <p className={styles.cardTitle}>Deployment:</p>
              <p className={styles.cardAddress}>{pipeline.deployment.uri}</p>
            </>
          ) : (
            <>
              <p className={styles.cardTitle}>Status:</p>
              <p className={styles.cardAddress}>{pipeline.status}</p>
            </>
          )}
        </div>
      </div>
    </a>
  );
}

export { PipelineCard };
