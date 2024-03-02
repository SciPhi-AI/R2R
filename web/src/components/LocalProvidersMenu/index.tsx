import React from 'react';
import { useRouter } from 'next/router';
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

export default function LocalProvidersMenu() {
  const router = useRouter();

const handleOnClick = (event, currentMenuItem) => {
  event.preventDefault();
  router.push(currentMenuItem.path);
};
    router.push(currentMenuItem.path);
    // console.log('Current Menu Item:', currentMenuItem);
    // console.log('Routing to:', currentMenuItem.path);
  };

  return (
    <div className={styles.menu}>
      {menuItems.map((menuItem) => (
        <span
          key={menuItem.name}
          className={styles.menuItem}
          onClick={() => handleOnClick(menuItem)}
        >
          {menuItem.name}
        </span>
      ))}
    </div>
  );
}
