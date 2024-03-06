// External imports
import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';

// Components and styles
import { NavItemHighlight } from '../NavItemHighlight';
import styles from './styles.module.scss';

// TypeScript interfaces for state
interface NavItemHighlightProps {
  width: number;
  translateX: number;
}

interface NavItem {
  path: string;
  label: string;
  width: number;
  translateX: number;
}

export function SubNavigationMenu() {
  const [isScrolling, setIsScrolling] = useState<boolean>(false);
  const [navItemHighlightPropsValues, setNavItemHighlightsPropsValues] =
    useState<NavItemHighlightProps | null>(null);

  const router = useRouter();
  const { pipelineId } = router.query;

  const navItems: NavItem[] = [
    { path: '/', label: 'Home', width: 60, translateX: 0 },
    {
      path: `/pipeline/${pipelineId}`,
      label: 'Pipeline',
      width: 80,
      translateX: 60,
    },
    { path: '/retrievals', label: 'Retrievals', width: 90, translateX: 140 },
    { path: '/embeddings', label: 'Embeddings', width: 100, translateX: 230 },
  ];

  useEffect(() => {
    const handleScroll = () => setIsScrolling(window.scrollY > 80);
    window.addEventListener('scroll', handleScroll, false);
    return () => window.removeEventListener('scroll', handleScroll, false);
  }, []);

  useEffect(() => {
    const activeItem = navItems.find((item) => router.pathname === item.path);
    setNavItemHighlightsPropsValues(
      activeItem
        ? { width: activeItem.width, translateX: activeItem.translateX }
        : null
    );
  }, [router.pathname]);

  const handleHoverNavItem = (event: React.MouseEvent<HTMLAnchorElement>) => {
    const itemPath = event.currentTarget.getAttribute('href');
    const hoveredItem = navItems.find((item) => item.path === itemPath);
    if (hoveredItem) {
      setNavItemHighlightsPropsValues({
        width: hoveredItem.width,
        translateX: hoveredItem.translateX,
      });
    }
  };

  return (
    <div className={styles.container}>
      <nav
        onMouseLeave={() => setNavItemHighlightsPropsValues(null)}
        className={`${styles.subNavigationMenu} ${isScrolling ? styles.scrollingContent : ''}`}
      >
        {navItemHighlightPropsValues && (
          <NavItemHighlight
            width={navItemHighlightPropsValues.width}
            translateX={navItemHighlightPropsValues.translateX}
          />
        )}
        {navItems.map((item) => (
          <Link
            key={item.path}
            href={item.path}
            onMouseOver={handleHoverNavItem}
            className={router.pathname === item.path ? styles.selected : ''}
          >
            {item.label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
