import Image from 'next/image';
import Link from 'next/link';

import styles from './styles.module.scss';
import { WorkspacesSelect } from '@/components/Layout/WorkspacesSelect';

export function MainMenu() {
  return (
    <div className={styles.container}>
      <WorkspacesSelect />

      <div className={styles.leftMainMenuNavigation}>
        {/* <button>Feedback</button>
        <button>Changelog</button>
        <button>Support</button> */}
        <Link
          href="https://docs.sciphi.ai"
          style={{ cursor: 'pointer' }}
          target="_blank"
          rel="noopener noreferrer"
        >
          Docs
        </Link>

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
