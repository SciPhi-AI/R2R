import Link from 'next/link';
import { useRouter } from 'next/router';
import { useEffect, useState, useRef } from 'react';
import { createClient } from '@/utils/supabase/component';
import { useAuth } from '@/context/authProvider';

import styles from './styles.module.scss';
import { NavItemHighlight } from '../NavItemHighlight';
import { Pipeline } from '@/types';

export function SubNavigationMenu() {
  const [isScrolling, setIsScrolling] = useState<boolean>(false);
  const [navItemHighlightPropsValues, setNavItemHighlightsPropsValues] =
    useState<{
      width: number;
      translateX: number;
      translateY?: number;
    } | null>(null);

  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const supabase = createClient();
  const pipelinesRef = useRef(pipelines);
  const { cloudMode } = useAuth();

  const fetchPipelines = () => {
    if (cloudMode === 'cloud') {
      supabase.auth.getSession().then(({ data: { session } }) => {
        const token = session?.access_token;
        if (token) {
          fetch('/api/pipelines', {
            headers: new Headers({
              Authorization: `Bearer ${token}`,
              'Content-Type': 'application/json',
            }),
          })
            .then((res) => {
              return res.json();
            })
            .then((json) => {
              console.log('json[pipelines] = ', json['pipelines']);
              setPipelines(json['pipelines']);
            });
        }
      });
    } else {
      fetch('/api/local_pipelines', {
        headers: new Headers({
          'Content-Type': 'application/json',
        }),
      })
        .then((res) => {
          return res.json();
        })
        .then((json) => {
          console.log('json[pipelines] = ', json['pipelines']);
          setPipelines(json['pipelines']);
        });
    }
  };

  useEffect(() => {
    pipelinesRef.current = pipelines;
  }, [pipelines]);

  useEffect(() => {
    fetchPipelines();
    const interval = setInterval(() => {
      // Use the current value of the pipelines ref
      if (
        pipelinesRef?.current?.some((pipeline) =>
          ['building', 'pending', 'deploying'].includes(pipeline.status)
        )
      ) {
        fetchPipelines();
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const router = useRouter();
  const { pipelineName } = router.query;
  const pipeline = pipelines.find((p) => p.id?.toString() === pipelineName);
  console.log('pipeline = ', pipeline);
  const pipelineId = pipeline?.id?.toString();
  console.log('pipelineId = ', pipelineId);

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
