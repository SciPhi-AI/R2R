import { FiExternalLink } from 'react-icons/fi';
import { useRouter } from 'next/router';
import React from 'react';

import styles from './styles.module.scss';
import { Pipeline } from '../../types';
import { useAuth } from '@/context/authProvider';

interface PipelineCardProps {
  pipeline: Pipeline;
}

export default function PipelineCard({ pipeline }: PipelineCardProps) {
  const router = useRouter();
  const { cloudMode } = useAuth();

  const handleClick = () => {
    if (cloudMode === 'cloud') {
      router.push(`/pipeline/${pipeline.id}`);
    } else {
      router.push(`/pipeline/${pipeline.id}/local_pipeline`);
    }
  };

  const terminal_message = pipeline?.deployment?.terminal_message;

  return (
    <a href="#" className={styles.container} onClick={handleClick}>
      <div className={styles.cardHeader}>
        <div className={styles.hoverRedirectIcon}>
          <FiExternalLink size="16" />
        </div>

        <div className={styles.projectInfo}>
          <p className={styles.cardTitle}>Pipeline:</p>
          <strong className={styles.cardProjectTitle}>{pipeline.name}</strong>
          {pipeline.status === 'finished' && (terminal_message===undefined || terminal_message==="") ? (
            <>
              <p className={styles.cardTitle}>Remote:</p>
              <p className={styles.cardAddress}>{pipeline.github_url}</p>

              <p className={styles.cardTitle}>Deployment:</p>
              <p className={styles.cardAddress}>{pipeline.deployment.uri}</p>
            </>
          ) : (
            <>
              <p className={styles.cardTitle}>Status:</p>
              <p className={styles.cardAddress}>
                {(terminal_message !== undefined && terminal_message.includes("failed"))? "FAILED": pipeline.status.toUpperCase()}
              </p>
            </>
          )}
        </div>
      </div>
    </a>
  );
}
