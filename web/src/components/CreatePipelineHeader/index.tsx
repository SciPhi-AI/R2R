import React from 'react';
import { useRouter } from 'next/router';
import { Button } from '@/components/Button';

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
    <div className="flex justify-between w-full">
      <Button
        className="h-10 w-40 py-2.5"
        variant="filled"
        onClick={createPipeline}
      >
        Create Pipeline
      </Button>
      <span className="font-bold ml-1 mt-2.5">
        {numPipelines}/10 pipelines deployed
      </span>
    </div>
  );
}
