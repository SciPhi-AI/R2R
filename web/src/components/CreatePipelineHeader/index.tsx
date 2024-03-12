import { useRouter } from 'next/router';
import React from 'react';

import { Button } from '@/components/ui/Button';

export function CreatePipelineHeader({
  numPipelines,
}: {
  numPipelines: number;
}) {
  const router = useRouter();

  const createPipeline = async () => {
    if (numPipelines >= 10) {
      alert(
        'You have reached the maximum number of pipelines. Please delete some pipelines before creating a new one.'
      );
    } else {
      router.push('/deploy');
    }
  };

  return (
    <div className="flex justify-between w-full">
      <Button
        className="h-10 w-40 py-2.5"
        variant={numPipelines >= 10 ? 'disabled' : 'filled'}
        onClick={createPipeline}
        disabled={numPipelines >= 10}
      >
        Create Pipeline
      </Button>
      <span className="font-bold ml-1 mt-2.5">
        {numPipelines}/10 pipelines deployed
      </span>
    </div>
  );
}
