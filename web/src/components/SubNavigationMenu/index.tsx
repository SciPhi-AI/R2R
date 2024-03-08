import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState, useRef } from 'react';
import { createClient } from '@/utils/supabase/component';
import { useAuth } from '@/context/authProvider';

import styles from './styles.module.scss';
import { NavItemHighlight } from '../NavItemHighlight';
import { Pipeline } from '@/types';

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
  const { cloudMode } = useAuth();
  const { pipelineName } = router.query;
  const pipeline = pipelines.find((p) => p.id?.toString() === pipelineName);
  const pipelineId = pipeline?.id?.toString();

  useEffect(() => {
    pipelinesRef.current = pipelines;
  }, [pipelines]);

  useEffect(() => {
    fetchPipelines();
    const interval = setInterval(() => {
      if (
        pipelinesRef.current.some((pipeline) =>
          ['building', 'pending', 'deploying'].includes(pipeline.status)
        )
      ) {
        fetchPipelines();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    getActiveNavItem();
  }, [router.pathname]);

  useEffect(() => {
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const fetchPipelines = async () => {
    const supabase = createClient();
    if (cloudMode === 'cloud') {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (token) {
        const response = await fetch('/api/pipelines', {
          headers: new Headers({
            Authorization: `Bearer ${token}`,
            'Content-Type': 'application/json',
          }),
        });
        const json = await response.json();
        setPipelines(json['pipelines']);
      }
    } else {
      const response = await fetch('/api/local_pipelines', {
        headers: new Headers({
          'Content-Type': 'application/json',
        }),
      });
      const json = await response.json();
      setPipelines(json['pipelines']);
    }
  };

  const navItems = [
    {
      path: '/',
      label: pipelineId ? '←' : 'Home',
      width: pipelineId ? 45 : 60,
      translateX: 0,
      translateY: 5,
    },
    ...(pipelineId
      ? [
          {
            path:
              cloudMode === 'cloud'
                ? `/pipeline/${pipelineId}`
                : `/pipeline/${pipelineId}/local_pipeline`,
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
    <div className={styles.container}>
      <nav
        onMouseLeave={handleLeaveNavItem}
        className={`${styles.subNavigationMenu} ${
          isScrolling ? styles.scrollingContent : ''
        }`}
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
