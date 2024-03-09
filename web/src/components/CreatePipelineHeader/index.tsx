import styles from './styles.module.scss';
import React from 'react';
import { useRouter } from 'next/router';

export function CreatePipelineHeader({
  numPipelines,
}: {
  numPipelines: number;
}) {
  const router = useRouter();

  const createPipeline = async () => {
    router.push('/deploy');
  };

  return (
    <div className="flex gap-4">
      <button
        className="bg-primary-custom text-color8 border border-color3 rounded-md h-10 w-40 px-2 py-1 text-md outline-none cursor-pointer transition-all duration-200 text-center hover:opacity-90 hover:border-solid hover:border-6 hover:border-color3 hover:text-color8"
        onClick={createPipeline}
      >
        New Pipeline
      </button>
      <span className="font-bold ml-1 mt-2.5">
        {numPipelines}/10 pipelines deployed
      </span>
    </div>
  );
}
