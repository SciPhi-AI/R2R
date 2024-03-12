import { useRouter } from 'next/router';
import React from 'react';

import styles from './styles.module.scss';

interface MenuItem {
  name: string;
  path: string;
  subset: string;
}

const menuItems = [
  {
    name: 'Databases',
    path: '/providers/databases',
    subset: 'vector-db-provider',
  },
  {
    name: 'Datasets',
    path: '/providers/datasets',
    subset: 'dataset-provider',
  },
  {
    name: 'LLMs',
    path: '/providers/large-language-models',
    subset: 'llm_provider',
  },
  {
    name: 'Integrations',
    path: '/providers/integrations',
    subset: 'integration',
  },
];

export default function ProvidersNavMenu() {
  const router = useRouter();

  const handleOnClick = (event, currentMenuItem) => {
    event.preventDefault();
    router.push(currentMenuItem.path);
  };

  return (
    <div className={styles.menu}>
      {menuItems.map((menuItem) => (
        <span
          key={menuItem.name}
          className={styles.menuItem}
          onClick={(event) => handleOnClick(event, menuItem)}
        >
          {menuItem.name}
        </span>
      ))}
    </div>
  );
}
