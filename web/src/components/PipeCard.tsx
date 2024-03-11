'use client';

import Link from 'next/link';
import { FiExternalLink } from 'react-icons/fi';
import {
  motion,
  useMotionTemplate,
  MotionValue,
  useMotionValue,
} from 'framer-motion';
import { useRouter } from 'next/router';

import { GridPattern } from '@/components/GridPattern';
import { UserIcon } from '@/components/icons/UserIcon';

function ResourceIcon({
  icon: Icon,
}: {
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-zinc-900/5 ring-1 ring-zinc-900/25 backdrop-blur-sm transition duration-300 group-hover:bg-white/50 group-hover:ring-zinc-900/25 dark:bg-white/7.5 dark:ring-white/15 dark:group-hover:bg-emerald-300/10 dark:group-hover:ring-emerald-400">
      <Icon className="h-5 w-5 fill-zinc-700/10 stroke-zinc-700 transition-colors duration-300 group-hover:stroke-zinc-900 dark:fill-white/10 dark:stroke-zinc-400 dark:group-hover:fill-emerald-300/10 dark:group-hover:stroke-emerald-400" />
    </div>
  );
}

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

export function PipeCard({ pipeline }) {
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

  return (
    <div
      onClick={handleClick}
      onMouseMove={onMouseMove}
      className="group relative flex cursor-pointer rounded-2xl bg-transparent transition-shadow hover:shadow-md hover:shadow-zinc-900/5 dark:bg-white/2.5 dark:hover:shadow-black/5"
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
          <p className="mt-1 overflow-hidden text-ellipsis whitespace-nowrap w-46">
            Pipeline:
          </p>
          <strong className="font-medium text-[var(--color-8)] overflow-hidden text-ellipsis whitespace-nowrap w-46">
            {pipeline.name}
          </strong>
          {pipeline.status === 'finished' ? (
            <>
              <p className="mt-1 overflow-hidden text-ellipsis whitespace-nowrap w-46">
                Remote:
              </p>
              <p className="overflow-hidden text-ellipsis whitespace-nowrap w-46">
                {pipeline.github_url}
              </p>

              <p className="mt-1 overflow-hidden text-ellipsis whitespace-nowrap w-46">
                Deployment:
              </p>
              <p className="overflow-hidden text-ellipsis whitespace-nowrap w-46">
                {pipeline.deployment.uri}
              </p>
            </>
          ) : (
            <>
              <p className="mt-1 overflow-hidden text-ellipsis whitespace-nowrap w-46">
                Status:
              </p>
              <p className="overflow-hidden text-ellipsis whitespace-nowrap w-46">
                {pipeline.status.toUpperCase()}
              </p>
            </>
          )}
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
