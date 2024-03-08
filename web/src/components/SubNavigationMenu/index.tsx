import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';

import styles from './styles.module.scss';
import { NavItemHighlight } from '../NavItemHighlight';

export function SubNavigationMenu() {
  const [isScrolling, setIsScrolling] = useState<boolean>(false);
  const [navItemHighlightPropsValues, setNavItemHighlightsPropsValues] =
    useState<{
      width: number;
      translateX: number;
      translateY?: number;
    } | null>(null);

  const router = useRouter();
  const { pipelineId } = router.query;

  const navItems = [
    {
      path: '/',
      label: '←',
      width: 45,
      translateX: 0,
      translateY: 5,
    },
    {
      path: `/pipeline/${pipelineId}`,
      label: 'Pipeline',
      width: 72,
      translateX: 45,
      translateY: 5,
    },
    {
      path: `/pipeline/${pipelineId}/retrievals`,
      label: 'Retrievals',
      width: 90,
      translateX: 117,
      translateY: 5,
    },
    {
      path: `/pipeline/${pipelineId}/embeddings`,
      label: 'Embeddings',
      width: 100,
      translateX: 207,
      translateY: 5,
    },
  ];

  // Function to determine active nav item based on current location
  function getActiveNavItem() {
    const activeItem = navItems.find((item) => router.pathname === item.path);
    if (activeItem) {
      setNavItemHighlightsPropsValues({
        width: activeItem.width,
        translateX: activeItem.translateX,
      });
    } else {
      setNavItemHighlightsPropsValues(null); // Reset if no active item is found
    }
  }

  useEffect(() => {
    getActiveNavItem();
  }, [router.pathname]);

  function handleHoverNavItem(event: React.MouseEvent<HTMLAnchorElement>) {
    const navItemElement = event.currentTarget;
    const itemPath = navItemElement.getAttribute('href');
    const hoveredItem = navItems.find((item) => item.path === itemPath);
    if (hoveredItem) {
      setNavItemHighlightsPropsValues({
        width: hoveredItem.width,
        translateX: hoveredItem.translateX,
        translateY: hoveredItem.translateY,
      });
    }
  }

  function handleLeaveNavItem() {
    getActiveNavItem();
  }

  // handle scroll
  function handleScroll() {
    if (window.scrollY > 80) {
      setIsScrolling(true);
    } else {
      setIsScrolling(false);
    }
  }

  useEffect(() => {
    window.addEventListener('scroll', handleScroll, false);
  }, [isScrolling]);

  return (
    <div className={styles.container}>
      <nav
        onMouseLeave={handleLeaveNavItem}
        className={`${styles.subNavigationMenu} ${isScrolling ? styles.scrollingContent : ''}`}
      >
        {navItemHighlightPropsValues != null ? (
          <NavItemHighlight
            width={navItemHighlightPropsValues.width}
            translateX={navItemHighlightPropsValues.translateX}
            translateY={navItemHighlightPropsValues.translateY}
          />
        ) : (
          ''
        )}
        {navItems.map((item) => (
          <Link
            key={item.path}
            href={item.path}
            onMouseOver={(event) => handleHoverNavItem(event)}
            className={router.pathname === item.path ? styles.selected : ''}
            style={{
              fontSize: item.label === '←' ? '1.5rem' : 'inherit',
            }}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
