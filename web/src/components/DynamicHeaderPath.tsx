import React, { useEffect, useState, useRef } from 'react';

import { Logo } from '@/components/Logo';
import { Code } from '@/components/Code';

import { useRouter } from 'next/router';
import { Pipeline } from '@/types';

const DynamicHeaderPath = ({ user }) => {
  const [isScrolling, setIsScrolling] = useState(false);
  const [navItemHighlightProps, setNavItemHighlightProps] = useState<{
    width: number;
    translateX: number;
    translateY?: number;
  } | null>(null);
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const pipelinesRef = useRef(pipelines);
  const router = useRouter();

  const userNameOrWorkspace =
    user && user.email ? user.email.split('@')[0] : 'workspace';

  const isHomePage = router.pathname === '/';
  const { pipelineName } = !isHomePage
    ? router.query
    : { pipelineName: '1234' };
  const pipelineShortId = (pipelineName as string).substring(0, 4);

  const determineTextBasedOnUrl = () => {
    const path = router.asPath;
    const match = path.match(/\/pipeline\/([^\/]+)\/?(.*)?/);
    return (match && match[2] ? match[2] : 'idx') + '.txt';
  };

  useEffect(() => {
    pipelinesRef.current = pipelines;
  }, [pipelines]);

  return (
    <div>
      <ul role="list" className="flex items-center gap-3">
        <Logo width={27} height={27} />
        <Code>
          <span className="text-zinc-800 dark:text-zinc-400">r2r_rag </span>/{' '}
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
          <span className="text-indigo-500">{userNameOrWorkspace}</span>
        </Code>
        {isHomePage && (
          <>
            <Code>|</Code>
            <Code>
              <span className="text-zinc-800 dark:text-zinc-400">grep</span>
            </Code>
            <Code>
              <span className="text-indigo-500">
                pipeline-{pipelineShortId}...
              </span>
            </Code>
            <Code>
              <span className="text-zinc-800 dark:text-zinc-400">
                {`>> ${determineTextBasedOnUrl()}`}
              </span>
            </Code>
          </>
        )}
      </ul>
    </div>
  );
};

export default DynamicHeaderPath;
