import React, { useEffect, useState, useRef } from 'react';

import { Logo } from '@/components/Logo';
import { Code } from '@/components/Code';

import { useRouter } from 'next/router';
import { Pipeline } from '@/types';

const DynamicHeaderPath = ({ user }) => {
  const [pipelines, setPipelines] = useState<Pipeline[]>([]);
  const pipelinesRef = useRef(pipelines);
  const router = useRouter();

  const userNameOrWorkspace =
    user && user.email ? user.email.split('@')[0] : 'workspace';

  const isPipelineRoute = router.pathname.includes('/pipeline/');
  const pathSegments = isPipelineRoute
    ? router.asPath.split('/').filter(Boolean)
    : [];
  const pipelineId = pathSegments.length > 1 ? pathSegments[1] : null;
  const afterPipelineSegment = pathSegments.length > 2 ? pathSegments[2] : null;

  useEffect(() => {
    pipelinesRef.current = pipelines;
  }, [pipelines]);

  const redirectToHome = () => {
    router.push('/');
  };

  return (
    <div>
      <ul role="list" className="flex items-center gap-3">
        <Logo width={27} height={27} />
        <Code onClick={redirectToHome} style={{ cursor: 'pointer' }}>
          <span className="text-zinc-800 dark:text-zinc-400">r2r_rag </span>|{' '}
        </Code>
        <div
          aria-label="Home"
          className="h-5 w-5 rounded-full"
          style={{
            background:
              'linear-gradient(90deg, #1f005c, #5b0060, #870160, #ac255e, #ca485c, #e16b5c, #f39060, #ffb56b)',
          }}
        ></div>
        <Code onClick={redirectToHome} style={{ cursor: 'pointer' }}>
          <span className="text-indigo-500">{userNameOrWorkspace}</span>
        </Code>
        {isPipelineRoute && (
          <>
            <Code>{`>>`}</Code>
            <Code>
              <span className="text-indigo-500">
                {afterPipelineSegment
                  ? `${afterPipelineSegment}:`
                  : 'pipeline:'}
              </span>
            </Code>
            <Code>
              <span className="text-zinc-400">{pipelineId}</span>
            </Code>
          </>
        )}
      </ul>
    </div>
  );
};

export default DynamicHeaderPath;
