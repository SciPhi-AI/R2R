import { useState } from 'react';

import Link from 'next/link';
import { FaGithub, FaTwitter, FaRegMoon } from 'react-icons/fa';
import { FiExternalLink } from 'react-icons/fi';

import styles from './styles.module.scss';
import { ArrowIcon } from '../ArrowIcon';

function Footer() {
  const [theme, setTheme] = useState('dark');

  const handleThemeChange = (event) => {
    setTheme(event.target.value);
  };
  return (
    <footer className={styles.container}>
      <div className={styles.categoryMenu}>
        <ul className={styles.category}>
          <Link href="https://github.com/SciPhi-AI/R2R" passHref>
            <li className={styles.categoryTitle}>R2R Framework</li>
          </Link>
        </ul>

        <ul className={styles.category}>
          <Link href="https://github.com/SciPhi-AI/agent-search" passHref>
            <li className={styles.categoryTitle}>Documentation</li>
          </Link>
        </ul>

        <ul className={styles.category}>
          <Link href="https://github.com/SciPhi-AI/R2R/commits/main/" passHref>
            <li className={styles.categoryTitle}>ChangeLog</li>
          </Link>
        </ul>

        <ul className={styles.category}>
          <Link href="https://docs.sciphi.ai/" passHref>
            <li className={styles.categoryTitle}>Agent Search</li>
          </Link>
        </ul>
      </div>

      <div className={styles.bottomPanel}>
        <div className={styles.bottomInfoPanel}>
          <div className={styles.redirectGroupButtons}>
            <Link href="https://github.com/SciPhi-AI/R2R" passHref>
              <FaGithub size="20" />{' '}
            </Link>
            <div className={styles.divider}></div>
            <Link href="https://twitter.com/ocolegro?lang=en" passHref>
              <FaTwitter size="20" />{' '}
            </Link>
          </div>
          <p className={styles.subText}>Copyright © 2024 SciPhi</p>

          {/* <div className={styles.selectContainer}>
            <FaRegMoon size="12" className={styles.selectPrefix} />

            <select
              className={styles.themeSelect}
              value={theme}
              onChange={handleThemeChange}
            >
              <option value="system">System</option>
              <option value="dark">Dark</option>
              <option value="light">Light</option>
            </select>
            <ArrowIcon id={styles.arrowMenuIcon} />
          </div> */}
        </div>
      </div>
    </footer>
  );
}

export { Footer };
