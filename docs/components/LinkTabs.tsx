import { Tabs as NextraTabs } from 'nextra/components';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';

export function LinkTabs({ items, children }) {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState(0);

  console.log('activeTab = ', activeTab)
  useEffect(() => {
    const queryTab = router.query.tab;
    if (queryTab) {
      const tabIndex = items.indexOf(queryTab);
      if (tabIndex !== -1) {
        setActiveTab(tabIndex);
      }
    }
  }, [router.query.tab, items]);

  const handleTabClick = (index) => {
    setActiveTab(index);
    router.push({
      query: { tab: items[index] }
    }, undefined, { shallow: true });
  };

  return (
    <NextraTabs items={items} selectedIndex={String(activeTab)} onChange={handleTabClick}>
      {children}
    </NextraTabs>
  );
}

LinkTabs.Tab = NextraTabs.Tab;