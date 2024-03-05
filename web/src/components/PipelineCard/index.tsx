import Image from 'next/image';
import { FaGithub } from 'react-icons/fa';
import { FiExternalLink } from 'react-icons/fi';
import { IoAnalyticsOutline } from 'react-icons/io5';

import styles from './styles.module.scss';
import { Pipeline } from '../../types';

interface CardProps {
  pipeline: Pipeline;
}

function Card({ pipeline }: CardProps) {
  console.log('pipeline = ', pipeline)
  return (
    <a href="#" className={styles.container}>
      <div className={styles.cardHeader}>
        <div className={styles.hoverRedirectIcon}>
          <FiExternalLink size="16" />
        </div>

        <div className={styles.imageContainer}>
          {/* <Image
            alt={`sciphi.png`}
            src={`/images/sciphi.png`}
            width={36}
            height={36}
            className={styles.cardProjectIcon}
          /> */}
        </div>

        <div className={styles.projectInfo}>
          <p className={styles.cardTitle}>Pipeline:</p>
          <strong className={styles.cardProjectTitle}>{pipeline.name}</strong>
          {pipeline.status == 'finished' ? (
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

export { Card };
