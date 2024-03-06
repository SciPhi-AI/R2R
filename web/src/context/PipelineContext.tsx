import React, { createContext, useContext, useState } from 'react';
import { useRouter } from 'next/router';
import { Pipeline } from '../types';

interface PipelineContextProps {
  pipeline: Pipeline;
  updatePipelineProp: <T extends keyof Pipeline>(
    propName: T,
    propValue: Pipeline[T]
  ) => void;
  navigateToPipeline: (pipelineId: number) => void;
}

const defaultPipeline: Pipeline = {
  id: 42,
  name: 'Default',
  deployment_url: 'https://example.com',
  github_url: 'https://github.com',
  status: 'active',
};

// Define a more precise type for the default context to avoid using empty functions
const defaultContextValue: PipelineContextProps = {
  pipeline: defaultPipeline,
  updatePipelineProp: () => {
    throw new Error('updatePipelineProp function should be implemented');
  },
  navigateToPipeline: () => {
    throw new Error('navigateToPipeline function should be implemented');
  },
};

const PipelineContext =
  createContext<PipelineContextProps>(defaultContextValue);

export const usePipelineContext = () => useContext(PipelineContext);

export const PipelineProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [pipeline, setPipeline] = useState<Pipeline>(defaultPipeline);
  const router = useRouter();

  const updatePipelineProp = <T extends keyof Pipeline>(
    propName: T,
    propValue: Pipeline[T]
  ) => {
    setPipeline((prevPipeline) => ({
      ...prevPipeline,
      [propName]: propValue,
    }));
  };

  const navigateToPipeline = (pipelineId: number) => {
    router.push(`/pipeline/${pipelineId}`);
  };

  return (
    <PipelineContext.Provider
      value={{ pipeline, updatePipelineProp, navigateToPipeline }}
    >
      {children}
    </PipelineContext.Provider>
  );
};
