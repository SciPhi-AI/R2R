import { forwardRef } from 'react';
import Link from 'next/link';
import clsx from 'clsx';
import { motion, useScroll, useTransform } from 'framer-motion';

import { Button } from '@/components/ui/Button';
import { Logo } from '@/components/shared/Logo';
import { ThemeToggle } from '@/components/shared/ThemeToggle';
import { Code } from '@/components/ui/Code';

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

export const SubNavigationBar = forwardRef<
  React.ElementRef<'div'>,
  { className?: string }
>(function Header({ className }, ref) {
  let { scrollY } = useScroll();
  let bgOpacityLight = useTransform(scrollY, [0, 72], [0.5, 0.9]);
  let bgOpacityDark = useTransform(scrollY, [0, 72], [0.2, 0.8]);

  return (
    <motion.div
      ref={ref}
      className={clsx(
        className,
        'fixed inset-x-0 top-10 z-40 flex h-10 items-center justify-between gap-12 px-4 transition sm:px-6 lg:z-30 lg:px-8 backdrop-blur-sm dark:backdrop-blur bg-zinc-800'
      )}
      style={
        {
          '--bg-opacity-light': bgOpacityLight,
          '--bg-opacity-dark': bgOpacityDark,
        } as React.CSSProperties
      }
    >
      <div className="flex items-center justify-between w-full">
        <div className="flex">
          {/* Left side of the navbar */}
          <nav>
            <ul role="list" className="flex items-center gap-3">
              <Logo width={27} height={27} />
              <Code>
                <span className="text-zinc-400">r2r_rag </span>/{' '}
              </Code>
              <div
                aria-label="Home"
                className="h-5 w-5 rounded-full"
                style={{
                  background:
                    'linear-gradient(90deg, #1f005c, #5b0060, #870160, #ac255e, #ca485c, #e16b5c, #f39060, #ffb56b)',
                }}
              ></div>
              <Code>
                <span className="text-indigo-500">jcllobet</span>
              </Code>
              <Code>|</Code>
              <Code>
                <span className="text-zinc-400">grep</span>
              </Code>
              <Code>
                <span className="text-indigo-500">pipeline-1234...</span>
              </Code>
              <Code>
                <span className="text-zinc-400">{`>> idx.txt`}</span>
              </Code>
            </ul>
          </nav>
        </div>
        {/* Right side of the navbar */}
        <div className="flex items-center gap-5">
          {/* This nav is hidden on mobile and visible from md screen size and up */}
          <nav className="hidden md:flex">
            <ul role="list" className="flex items-center gap-8">
              <TopLevelNavItem href="https://docs.sciphi.ai/">
                Documentation
              </TopLevelNavItem>
              <TopLevelNavItem href="https://discord.gg/p6KqD2kjtB">
                Support
              </TopLevelNavItem>
            </ul>
          </nav>
          {/* This divider is hidden on mobile and visible from md screen size and up */}
          <div className="hidden md:block md:h-5 md:w-px md:bg-zinc-900/10 md:dark:bg-white/15"></div>
          <div className="flex gap-4">
            {/* <ThemeToggle /> */}
            {/* This div is hidden until the screen width reaches 416px */}
            <div className="hidden min-[416px]:contents">
              <Button>Sign in</Button>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
});
