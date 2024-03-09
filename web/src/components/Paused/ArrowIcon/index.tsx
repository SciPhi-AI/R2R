import { SelectHTMLAttributes } from 'react';
import { MdKeyboardArrowUp, MdKeyboardArrowDown } from 'react-icons/md';

import styles from './styles.module.scss';

function ArrowIcon(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <span {...props} className={styles.arrowIcon}>
      <MdKeyboardArrowUp size="12" className={styles.topSpace} />

      <MdKeyboardArrowDown size="12" className={styles.bottomSpace} />
    </span>
  );
}

export { ArrowIcon };
