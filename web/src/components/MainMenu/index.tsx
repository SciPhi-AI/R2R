import Image from 'next/image';

import styles from './styles.module.scss';
import { WorkspacesSelect } from '../WorkspacesSelect';

export function MainMenu() {
  return (
    <div className={styles.container}>
      <WorkspacesSelect />

      <div className={styles.leftMainMenuNavigation}>
        {/* <button>Feedback</button>
        <button>Changelog</button>
        <button>Support</button> */}
        <a
          style={{ cursor: 'pointer' }}
          href="https://docs.sciphi.ai"
          target="_blank"
          rel="noopener noreferrer"
        >
          <button>Docs</button>
        </a>

        <div>
          <Image
            src="/images/dummy_logo.png"
            alt="Acme Co."
            width="28"
            height="28"
            className={styles.userIcon}
          />
        </div>
      </div>
    </div>
  );
}
