import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState, useRef } from 'react';
import { NavItemHighlight } from '../NavItemHighlight';
import { Pipeline } from '@/types';

function HomePageNav() {
  return (
    <div className="sticky top-0 flex flex-row items-center bg-[var(--sciphi-top-bg)] px-[14rem] py-1 z-10 backdrop-blur-lg min-h-[60px]">
      {/* Content specific to the homepage navigation can go here */}
    </div>
  );
}

function OtherPageNav({
  navItems,
  navItemHighlightProps,
  handleHoverNavItem,
  handleLeaveNavItem,
  router,
  isScrolling,
}) {
  return (
    <div className="sticky top-0 flex flex-row items-center bg-[var(--sciphi-top-bg)] px-[14rem] py-1 z-10 backdrop-blur-lg">
      <nav
        onMouseLeave={handleLeaveNavItem}
        className={`cursor-pointer text-[0.95rem] text-[var(--color-5)] flex ${isScrolling ? 'pt-[0.6rem] translate-x-[0.4rem] z-10' : ''}`}
      >
        {navItemHighlightProps && (
          <NavItemHighlight
            width={navItemHighlightProps.width}
            translateX={navItemHighlightProps.translateX}
            translateY={navItemHighlightProps.translateY}
          />
        )}
        {navItems.map((item) => (
          <Link
            key={item.path}
            href={item.path}
            onMouseOver={handleHoverNavItem}
            className={`${router.pathname === item.path ? 'text-[var(--color-8)] relative flex items-center justify-center rounded-[4px] px-[11px] py-[6px] transition-colors duration-200 ease-in-out' : ''}`}
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

export function SubNavigationMenu() {
  const [isScrolling, setIsScrolling] = useState(false);
  const [navItemHighlightProps, setNavItemHighlightProps] = useState<{
    width: number;
    translateX: number;
    translateY?: number;
  } | null>(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const pipelinesRef = useRef(pipelines);

  const router = useRouter();
  const { pipelineName } = router.query;
  const pipelineId = pipelineName as string;
  const isHomePage = router.pathname === '/';

  useEffect(() => {
    pipelinesRef.current = pipelines;
  }, [pipelines]);

  useEffect(() => {
    getActiveNavItem();
  }, [router.pathname]);

  useEffect(() => {
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const navItems = [
    {
      path: '/',
      label: '←',
      width: 45,
      translateX: 0,
      translateY: 5,
    },
    ...(pipelineId
      ? [
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
        ]
      : []),
  ];

  const getActiveNavItem = () => {
    const activeItem = navItems.find((item) => router.pathname === item.path);
    if (activeItem) {
      setNavItemHighlightProps({
        width: activeItem.width,
        translateX: activeItem.translateX,
      });
    } else {
      setNavItemHighlightProps(null);
    }
  };

  const handleHoverNavItem = (event: React.MouseEvent<HTMLAnchorElement>) => {
    const navItemElement = event.currentTarget;
    const itemPath = navItemElement.getAttribute('href');
    const hoveredItem = navItems.find((item) => item.path === itemPath);
    if (hoveredItem) {
      setNavItemHighlightProps({
        width: hoveredItem.width,
        translateX: hoveredItem.translateX,
        translateY: hoveredItem.translateY,
      });
    }
  };

  const handleLeaveNavItem = () => {
    getActiveNavItem();
  };

  const handleScroll = () => {
    setIsScrolling(window.scrollY > 80);
  };

  return (
    <>
      {isHomePage ? (
        <HomePageNav />
      ) : (
        <OtherPageNav
          navItems={navItems}
          navItemHighlightProps={navItemHighlightProps}
          handleHoverNavItem={handleHoverNavItem}
          handleLeaveNavItem={handleLeaveNavItem}
          router={router}
          isScrolling={isScrolling}
        />
      )}
    </>
  );
}
