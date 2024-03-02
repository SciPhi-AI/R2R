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
    } | null>(null);

  const router = useRouter();

  const navItems = [
    { path: '/retrievals', width: 85.3, translateX: 0 },
    { path: '/embeddings', width: 100, translateX: 87.5 },
    // { path: '/providers/databases', width: 75, translateX: 68 },
  ];

  // Function to determine active nav item based on current location
  function getActiveNavItem() {
    const activeItem = navItems.find((item) => location.pathname === item.path);
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

  function handleHoverNavItem(index: number) {
    const navItem = navItems[index];
    if (navItem) {
      setNavItemHighlightsPropsValues({
        width: navItem.width,
        translateX: navItem.translateX,
      });
    } else {
      setNavItemHighlightsPropsValues(null);
    }
  }

  function handleLeaveNavItem() {
    setNavItemHighlightsPropsValues(null);
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
          />
        ) : (
          ''
        )}
        <Link href="/retrievals" passHref legacyBehavior>
          <a
            onMouseOver={() => handleHoverNavItem(0)}
            className={router.pathname === '/retrievals' ? styles.selected : ''}
          >
            Retrievals
          </a>
        </Link>
        <Link href="/embeddings" passHref legacyBehavior>
          <a
            onMouseOver={() => handleHoverNavItem(1)}
            className={router.pathname === '/embeddings' ? styles.selected : ''}
          >
            Embeddings
          </a>
        </Link>

        {/* <Link href="/providers/databases" passHref legacyBehavior>
          <a
            onMouseOver={() => handleHoverNavItem(1)}
            className={
              router.pathname === '/providers/databases' ? styles.selected : ''
            }
          >
            Providers
          </a>
        </Link> */}
      </nav>
    </div>
  );
}
