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
  return (
    <a href="#" className={styles.container}>
      <div className={styles.cardHeader}>
        <div className={styles.hoverRedirectIcon}>
          <FiExternalLink size="16" />
        </div>

        <div className={styles.imageContainer}>
          <Image
            alt={`sciphi.png`}
            src={`/images/sciphi.png`}
            width={36}
            height={36}
            className={styles.cardProjectIcon}
          />
        </div>

        <div className={styles.projectInfo}>
          <strong className={styles.cardProjectTitle}>{pipeline.name}</strong>
          <p className={styles.cardDomainAddress}>{pipeline.deployment_url}</p>
        </div>
      </div>

      <button className={styles.cardButtonEnableAnalytics}>
        <IoAnalyticsOutline size="18" />
      </button>

      <div className={styles.cardProjectLastCommit}>
        {pipeline.last_commit_name}
      </div>

      <div className={styles.cardLastModificationsAt}>
        {pipeline.updated_at.when}
        {pipeline.updated_at.from_other_services &&
        pipeline.updated_at.service ? (
          <FaGithub size="17" />
        ) : (
          ''
        )}
      </div>
    </a>
  );
}

export { Card };
