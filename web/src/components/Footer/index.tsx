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
          <li className={styles.categoryTitle}>Frameworks</li>

          <li className={styles.categoryItem}>R2R</li>
          <li className={styles.categoryItem}>Agent Search</li>
          <li className={styles.categoryItem}>Observability</li>
          <li className={styles.categoryItem}>Eval</li>
          <li className={styles.categoryItem}>Orchestration</li>
        </ul>

        <ul className={styles.category}>
          <li className={styles.categoryTitle}>Resources</li>

          <li className={styles.categoryItem}>Documentation</li>
          <li className={styles.categoryItem}>Guides</li>
          <li className={styles.categoryItem}>Support</li>
          <li className={styles.categoryItem}>API Reference</li>
          <li className={styles.categoryItem}>Integrations</li>
        </ul>

        <ul className={styles.category}>
          <li className={styles.categoryTitle}>Company</li>

          <li className={styles.categoryItem}>Home</li>
          <li className={styles.categoryItem}>Changelog</li>
          <li className={styles.categoryItem}>Careers</li>
          <li className={styles.categoryItem}>Pricing</li>
          <li className={styles.categoryItem}>Contact Us</li>
        </ul>

        <ul className={styles.category}>
          <li className={styles.categoryTitle}>Legal</li>

          <li className={styles.categoryItem}>Privacy Policy</li>
          <li className={styles.categoryItem}>Terms of Service</li>
          <li className={styles.categoryItem}>Trademark Policy</li>
          <li className={styles.categoryItem}>Inactivity Policy</li>
          <li className={styles.categoryItem}>DMCA Policy</li>
        </ul>
      </div>

      <div className={styles.bottomPanel}>
        {/* basically it's the same Vercel logo from the site */}

        <div className={styles.bottomInfoPanel}>
          <p className={styles.subText}>Copyright © 2024 SciPhi</p>

          <div className={styles.redirectGroupButtons}>
            <Link href="https://github.com/SciPhi-AI/R2R" passHref>
              <FaGithub size="20" />{' '}
            </Link>
            <div className={styles.divider}></div>
            <Link href="https://twitter.com/ocolegro?lang=en" passHref>
              <FaTwitter size="20" />{' '}
            </Link>
          </div>
          <div className={styles.selectContainer}>
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
          </div>
        </div>
      </div>
    </footer>
  );
}

export { Footer };
