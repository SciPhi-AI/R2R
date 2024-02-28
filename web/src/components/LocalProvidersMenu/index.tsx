import React, { useEffect } from 'react';
import { useRouter } from 'next/router';
import styles from './styles.module.scss';
import { Provider } from '@/types';
import { useProviderDataContext } from '@/context/providerContext'; // Adjust the import path as necessary

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
  const { getAllProviders, getFilteredProviders } = useProviderDataContext();
  const currentPath = router.pathname;
  const currentMenuItem = menuItems.find((item) => item.path === currentPath);
  const providers = getAllProviders();

  const handleOnClick = (currentMenuItem) => {
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
