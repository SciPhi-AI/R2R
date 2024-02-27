import React from 'react';
import { useRouter } from 'next/router';
import styles from './styles.module.scss'; // Import the styles

const menuItems = [
  { name: 'Databases', path: '/providers/databases' },
  { name: 'Datasets', path: '/providers/datasets' },
  { name: 'LLMs', path: '/providers/large-language-models' },
  { name: 'Integrations', path: '/providers/integrations' },
];

export default function LocalProvidersMenu() {
  const router = useRouter();
  const currentPath = router.pathname;

  return (
    <div className={styles.menu}>
      {menuItems.map((item) => (
        <span
          key={item.path}
          className={`${styles.menuItem} ${currentPath === item.path ? styles.active : ''}`}
          onClick={() => router.push(item.path)}
        >
          {item.name}
        </span>
      ))}
    </div>
  );
}
