import Image from 'next/image';
import { FiExternalLink } from 'react-icons/fi';
import { IoAnalyticsOutline } from 'react-icons/io5';

import styles from './styles.module.scss';
import { Provider } from '../../../types';

interface CardProps {
  provider: Provider;
  onClick: () => void;
}

function IntegrationCard({ provider, onClick }: CardProps) {
  return (
    <a href="#" className={styles.container} onClick={onClick}>
      <div className={styles.cardHeader}>
        <div className={styles.hoverRedirectIcon}>
          <FiExternalLink size="16" />
        </div>
        <div className={styles.imageContainer}>
          <Image
            alt={provider.logo}
            src={`/images/${provider.logo}`}
            width={26}
            height={26}
            className={styles.cardProjectIcon}
          />
        </div>
        <div className={styles.projectInfo}>
          <strong className={styles.cardProjectTitle}>{provider.name}</strong>
        </div>
      </div>

      <button className={styles.cardButtonEnableAnalytics}>
        <IoAnalyticsOutline size="18" />
      </button>
    </a>
  );
}

export { IntegrationCard };
