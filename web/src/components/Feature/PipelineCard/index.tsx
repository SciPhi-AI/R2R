import { FiExternalLink } from 'react-icons/fi';
import Link from 'next/link';
import { usePipelineContext } from '@/context/PipelineContext';

import styles from './styles.module.scss';

interface PipelineCardProps {
  id: number;
}

function PipelineCard({ id }: PipelineCardProps) {
  const { pipeline } = usePipelineContext();

  if (!pipeline) {
    // Handle the case where pipeline is null or render nothing or a loader
    return <div>Loading...</div>;
  }

  return (
    <Link href={`/pipeline/${pipeline.id}`} passHref>
      <a className={styles.container}>
        <div className={styles.cardHeader}>
          <div className={styles.hoverRedirectIcon}>
            <FiExternalLink size="16" />
          </div>

          <div className={styles.imageContainer}>
            {/* Image component commented out for brevity */}
          </div>

          <div className={styles.projectInfo}>
            <p className={styles.cardTitle}>Pipeline:</p>
            <strong className={styles.cardProjectTitle}>{pipeline.name}</strong>
            {pipeline.status === 'finished' ? (
              <>
                <p className={styles.cardTitle}>Remote:</p>
                <p className={styles.cardAddress}>{pipeline.github_url}</p>

                <p className={styles.cardTitle}>Deployment:</p>
                <p className={styles.cardAddress}>{pipeline.deployment_url}</p>
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
    </Link>
  );
}

export { PipelineCard };
