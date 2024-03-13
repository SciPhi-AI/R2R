import clsx from 'clsx';
import { motion, useScroll, useTransform } from 'framer-motion';
import Link from 'next/link';
import { useRouter } from 'next/router';
import { forwardRef, useEffect, useState, useRef } from 'react';

import { Button } from '@/components/ui/Button';
import { Pipeline } from '@/types';
import { createClient } from '@/utils/supabase/component';

import DynamicHeaderPath from './DynamicHeaderPath';
import { ProfileMenu } from './ProfileMenu';
import { SubNavigationBar } from './SubNavigationBar';

function TopLevelNavItem({
  href,
  children,
}: {
  href: string;
  children: React.ReactNode;
}) {
  return (
    <li>
      <Link
        href={href}
        className="text-sm leading-5 text-zinc-600 transition hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-white"
        legacyBehavior
      >
        {children}
      </Link>
    </li>
  );
}

export const Navbar = forwardRef<
  React.ElementRef<'div'>,
  { className?: string }
>(function Header({ className }, ref) {
  const supabase = createClient();
  const [user, setUser] = useState(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const pipelinesRef = useRef(pipelines);
  const router = useRouter();

  useEffect(() => {
    const fetchUser = async () => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      setUser(session?.user);
    };

    fetchUser();
  }, []);

  useEffect(() => {
    pipelinesRef.current = pipelines;
  }, [pipelines]);

  const { scrollY } = useScroll();
  const bgOpacityLight = useTransform(scrollY, [0, 72], [0.5, 0.9]);
  const bgOpacityDark = useTransform(scrollY, [0, 72], [0.2, 0.8]);

  // Determine the active segment for highlighting in SubNavigationBar
  const isPipelineRoute = router.pathname.includes('/pipeline/');
  const pathSegments = isPipelineRoute
    ? router.asPath.split('/').filter(Boolean)
    : [];
  const pipelineId = pathSegments.length > 1 ? pathSegments[1] : null;

  return (
    <>
      <motion.div
        ref={ref}
        className={clsx(
          className,
          'fixed inset-x-0 top-0 z-50 flex h-10 items-center justify-between gap-12 px-4 transition sm:px-6 lg:z-30 lg:px-8 backdrop-blur-sm dark:backdrop-blur bg-zinc-100 dark:bg-zinc-800'
        )}
        style={
          {
            '--bg-opacity-light': bgOpacityLight,
            '--bg-opacity-dark': bgOpacityDark,
          } as React.CSSProperties
        }
      >
        <nav className="flex items-center justify-between w-full">
          <div className="flex">
            {/* Left side of the navbar */}
            <DynamicHeaderPath user={user} pipelines={pipelines} />
          </div>
          {/* Right side of the navbar */}
          <div className="flex items-center gap-5">
            {/* This nav is hidden on mobile and visible from md screen size and up */}
            <nav className="hidden md:flex">
              <ul role="list" className="flex items-center gap-8">
                <TopLevelNavItem href="/docs">
                  <Button
                    className="rounded-md h-6 py-0.5 px-3 w-30"
                    variant="primary"
                  >
                    Docs
                  </Button>
                </TopLevelNavItem>
              </ul>
            </nav>
            {/* This divider is hidden on mobile and visible from md screen size and up */}
            <div className="hidden md:block md:h-5 md:w-px md:bg-zinc-900/10 md:dark:bg-white/15"></div>
            <div className="flex gap-4">
              {/* <ThemeToggle /> */}
              {/* This div is hidden until the screen width reaches 416px */}
              <div className="hidden min-[416px]:contents">
                <ProfileMenu user={user} />
              </div>
            </div>
          </div>
        </nav>
      </motion.div>
      <SubNavigationBar
        isPipelineRoute={isPipelineRoute}
        pipelineId={pipelineId}
        pathSegments={pathSegments}
      />
    </>
  );
});
