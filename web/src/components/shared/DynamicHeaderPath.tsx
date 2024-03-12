import React from 'react';
import { Logo } from '@/components/shared/Logo';
import { Code } from '@/components/ui/Code';
import { useRouter } from 'next/router';
import { Pipeline } from '@/types';

const capitalizeFirstLetter = (string) => {
  if (!string) return string;
  return string.charAt(0).toUpperCase() + string.slice(1);
};
const DynamicHeaderPath = ({
  user,
  pipelines,
}: {
  user: any;
  pipelines: Pipeline[];
}) => {
  const router = useRouter();

  const userNameOrWorkspace =
    user && user.email ? user.email.split('@')[0] : 'workspace';

  const isPipelineRoute = router.pathname.includes('/pipeline/');
  const pathSegments = isPipelineRoute
    ? router.asPath.split('/').filter(Boolean)
    : [];
  const pipelineId = pathSegments.length > 1 ? pathSegments[1] : null;
  const afterPipelineSegment = pathSegments.length > 2 ? pathSegments[2] : null;

  const redirectToHome = () => {
    router.push('/');
  };

  return (
    <div>
      <ul role="list" className="flex items-center gap-3">
        <Logo width={27} height={27} />
        <Code onClick={redirectToHome} style={{ cursor: 'pointer' }}>
          <span className="text-zinc-800 dark:text-zinc-400">SciPhi </span>|{' '}
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
                  ? `${capitalizeFirstLetter(afterPipelineSegment)}:`
                  : 'Pipeline:'}
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
