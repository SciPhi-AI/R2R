'use client';

import { FiExternalLink } from 'react-icons/fi';
import {
  motion,
  useMotionTemplate,
  MotionValue,
  useMotionValue,
} from 'framer-motion';
import { useRouter } from 'next/router';

import { GridPattern } from '@/components/shared/GridPattern';
import { Heading } from '@/components/shared/Heading';

function ResourcePattern({
  mouseX,
  mouseY,
  ...gridProps
}: { mouseX: MotionValue<number>; mouseY: MotionValue<number> } & Omit<
  React.ComponentPropsWithoutRef<typeof GridPattern>,
  'width' | 'height' | 'x'
>) {
  let maskImage = useMotionTemplate`radial-gradient(100px at ${mouseX}px ${mouseY}px, white, transparent)`;
  let style = { maskImage, WebkitMaskImage: maskImage };

  return (
    <div className="pointer-events-none">
      <div className="absolute inset-0 rounded-2xl transition duration-300 [mask-image:linear-gradient(white,transparent)] group-hover:opacity-50">
        <GridPattern
          width={72}
          height={56}
          x="50%"
          className="absolute inset-x-0 inset-y-[-30%] h-[160%] w-full skew-y-[-18deg] fill-black/[0.02] stroke-black/5 dark:fill-gray-600/10 dark:stroke-gray-800"
          {...gridProps}
        />
      </div>
      <motion.div
        className="absolute inset-0 rounded-2xl bg-gradient-to-r from-[rgb(7,7,7)] to-[rgb(16,255,3)] opacity-0 transition duration-300 group-hover:opacity-90 dark:from-indigo-600 dark:to-[#262b3c]"
        style={style}
      />
      <motion.div
        className="absolute inset-0 rounded-2xl opacity-0 mix-blend-overlay transition duration-300 group-hover:opacity-100"
        style={style}
      >
        <GridPattern
          width={72}
          height={56}
          x="50%"
          className="absolute inset-x-0 inset-y-[-30%] h-[160%] w-full skew-y-[-18deg] fill-black/50 stroke-black/70 dark:fill-white/2.5 dark:stroke-white/10"
          {...gridProps}
        />
      </motion.div>
    </div>
  );
}

export function PipeCard({
  pipeline,
  className,
}: {
  pipeline: any;
  className?: string;
}) {
  const router = useRouter();
  let mouseX = useMotionValue(0);
  let mouseY = useMotionValue(0);

  const handleClick = () => {
    router.push(`/pipeline/${pipeline.id}`);
  };

  function onMouseMove({
    currentTarget,
    clientX,
    clientY,
  }: React.MouseEvent<HTMLDivElement>) {
    let { left, top } = currentTarget.getBoundingClientRect();
    mouseX.set(clientX - left);
    mouseY.set(clientY - top);
  }

  function getStatusTagColor(
    status: string
  ): 'rose' | 'amber' | 'emerald' | 'zinc' | 'indigo' | 'sky' | null {
    switch (status.toUpperCase()) {
      case 'FAILED':
        return 'rose';
      case 'DEPLOYING':
        return 'amber';
      default:
        return null;
    }
  }

  const tagColor = getStatusTagColor(pipeline.status);

  function renderGithubUrl(status: string, url?: string): JSX.Element {
    let message;
    if (status === 'finished' && url) {
      message = url.slice(8, 37);
    } else if (status === 'deploying') {
      message = 'URL incoming upon completion';
    } else {
      message = 'Pipeline not finished';
    }

    return (
      <p className="overflow-hidden text-ellipsis whitespace-nowrap w-46">
        {message}
      </p>
    );
  }

  function renderDeploymentUri(status: string, uri?: string): JSX.Element {
    let message;
    if (status === 'finished' && uri) {
      message = uri.slice(8, 37);
    } else if (status === 'deploying') {
      message = 'Deployment incoming upon completion';
    } else {
      message = 'Deployment not available';
    }

    return (
      <p className="overflow-hidden text-ellipsis whitespace-nowrap w-46">
        {message}
      </p>
    );
  }

  return (
    <div
      onClick={handleClick}
      onMouseMove={onMouseMove}
      className={`group relative flex cursor-pointer rounded-2xl bg-transparent transition-shadow hover:shadow-md hover:shadow-zinc-900/5 dark:bg-white/2.5 dark:hover:shadow-black/5 ${className}`}
    >
      <ResourcePattern
        mouseX={mouseX}
        mouseY={mouseY}
        y={16}
        squares={[
          [0, 1],
          [1, 3],
        ]}
      />
      <div className="absolute inset-0 rounded-2xl ring-1 ring-inset ring-zinc-900/7.5 group-hover:ring-zinc-900/10 dark:ring-white/10 dark:group-hover:ring-white/20" />
      <div className="flex justify-between items-center relative rounded-2xl p-8 w-full">
        <div className="flex-1">
          <Heading
            level={3}
            id={`pipeline-${pipeline.id}`}
            {...(tagColor
              ? {
                  tag: pipeline.status.toUpperCase(),
                  tag_color: tagColor,
                }
              : {})}
            textColor="dark:text-zinc-500"
            anchor={false}
          >
            Pipeline
          </Heading>
          <Heading
            level={2}
            id={`pipeline-name-${pipeline.id}`}
            className="text-2xl font-medium"
            anchor={false}
          >
            {pipeline.name}
          </Heading>
          <>
            <p className="mt-1 overflow-hidden text-ellipsis dark:text-zinc-500 whitespace-nowrap w-46">
              Remote:
            </p>
            {pipeline.github_url
              ? renderGithubUrl('finished', pipeline.github_url)
              : renderGithubUrl(pipeline.status)}

            <p className="mt-1 overflow-hidden text-ellipsis dark:text-zinc-500 whitespace-nowrap w-46">
              Deployment:
            </p>
            {pipeline?.deployment?.uri
              ? renderDeploymentUri('finished', pipeline?.deployment?.uri)
              : renderDeploymentUri(pipeline.status)}
          </>
        </div>
        <div className="absolute top-0 right-0 mt-2 mr-2">
          <div className="bg-color7 p-2 rounded-full invisible group-hover:visible group-hover:animate-handleHoverLinkIconAnimation">
            <FiExternalLink size="16" className="text-color1" />
          </div>
        </div>
      </div>
    </div>
  );
}
