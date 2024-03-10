import Image from 'next/image';
import { useRouter } from 'next/router';

import styles from './styles.module.scss';

function WorkspacesSelect() {
  const router = useRouter();
  const pipelineId = router.asPath.split('/').pop();

  console.log('NavbarpipelineId = ', pipelineId);

  return (
    <>
      <Image
        alt={`sciphi.png`}
        src={`/images/sciphi.png`}
        width={30}
        height={30}
        className="cursor-pointer"
      />
      <div className={styles.divider}></div>

      <div className={styles.userPanel}>
        <div className={styles.currentWorkspace}>
          <div>
            <Image
              src="/images/dummy_logo.png"
              alt="Acme Co."
              width="30"
              height="30"
              className={styles.workspaceIcon}
            />
          </div>
          Acme Co.
        </div>
      </div>
      {router.pathname !== '/' && pipelineId && (
        <>
          <div className={styles.divider}></div>
          <div className={styles.userPanel}>
            Pipeline: <code>{pipelineId.slice(0, 8)}...</code>
          </div>
        </>
      )}
    </>
  );
}

export { WorkspacesSelect };
