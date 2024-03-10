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
import styles from './PipelineCard/styles.module.scss';

function ResourceIcon({
  icon: Icon,
}: {
  icon: React.ComponentType<{ className?: string }>;
}) {
  return (
    <div className="flex h-7 w-7 items-center justify-center rounded-full bg-zinc-900/5 ring-1 ring-zinc-900/25 backdrop-blur-[2px] transition duration-300 group-hover:bg-white/50 group-hover:ring-zinc-900/25 dark:bg-white/7.5 dark:ring-white/15 dark:group-hover:bg-emerald-300/10 dark:group-hover:ring-emerald-400">
      <Icon className="h-5 w-5 fill-zinc-700/10 stroke-zinc-700 transition-colors duration-300 group-hover:stroke-zinc-900 dark:fill-white/10 dark:stroke-zinc-400 dark:group-hover:fill-emerald-300/10 dark:group-hover:stroke-emerald-400" />
    </div>
  );
}
{
  /* Initially hidden GridPattern */
}
// className="absolute inset-x-0 inset-y-[-30%] h-[160%] w-full skew-y-[-18deg] fill-indigo-100 stroke-indigo-100 dark:fill-indigo-600 dark:stroke-indigo-600 opacity-10 group-hover:opacity-90"
{
  /* Adjusted opacity for hover effect */
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

export function ContactResource({ pipeline }) {
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
      onMouseMove={onMouseMove}
      className="group relative flex rounded-2xl bg-transparent transition-shadow hover:shadow-md hover:shadow-zinc-900/5 dark:bg-white/2.5 dark:hover:shadow-black/5"
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
      <div className="relative rounded-2xl p-8 ">
        <div className={styles.cardHeader}>
          <div className={styles.hoverRedirectIcon}>
            <FiExternalLink size="16" />
          </div>

          <div className={styles.projectInfo}>
            <p className={styles.cardTitle}>Pipeline:</p>
            <strong className={styles.cardProjectTitle}>{pipeline.name}</strong>
            {pipeline.status === 'finished' ? (
              <>
                <p className={styles.cardTitle}>Remote:</p>
                <p className={styles.cardAddress}>{pipeline.github_url}</p>

                <p className={styles.cardTitle}>Deployment:</p>
                <p className={styles.cardAddress}>{pipeline.deployment.uri}</p>
              </>
            ) : (
              <>
                <p className={styles.cardTitle}>Status:</p>
                <p className={styles.cardAddress}>
                  {pipeline.status.toUpperCase()}
                </p>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
