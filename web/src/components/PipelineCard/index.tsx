import { FiExternalLink } from 'react-icons/fi';
import { usePipelineContext } from '@/context/PipelineContext';
import { useRouter } from 'next/router';
import { useUpdatePipelineProp } from '@/hooks/useUpdatePipelineProp';

import styles from './styles.module.scss';
import { Pipeline } from '../../types';

interface PipelineCardProps {
  id: number; // Assuming id is of type number, adjust if necessary
}

function PipelineCard({ id }: PipelineCardProps) {
  const updatePipelineProp = useUpdatePipelineProp();
  const { pipeline } = usePipelineContext();
  const router = useRouter();

  const handleClick = () => {
    // Use the update function with the specific property name and value
    updatePipelineProp('id', pipeline.id);
    router.push(`/pipeline/${pipeline.id}`);
  };

  if (!pipeline) {
    // Handle the case where pipeline is null or render nothing or a loader
    return <div>Loading...</div>; // or any other fallback UI
  }

  return (
    <a href="#" className={styles.container} onClick={handleClick}>
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

        <div className={styles.projectInfo} id={`${id}`}>
          <p className={styles.cardTitle}>Pipeline:</p>
          <strong className={styles.cardProjectTitle}>{pipeline.name}</strong>
          {pipeline.status == 'finished' ? (
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
  );
}

export { PipelineCard };
