import { createContext, useContext, useState, useEffect } from 'react';

import { useAuth } from './authProvider';
import { Pipeline } from '../types'; // Import the Pipeline type

interface PipelineContextProps {
  pipelines: Record<string, Pipeline>;
  updatePipelines(pipelineId: string, pipeline: Pipeline): void;
}

const PipelineContext = createContext<PipelineContextProps>({
  pipelines: {},
  updatePipelines: () => {},
});

export const usePipelineContext = () => useContext(PipelineContext);

export const PipelineProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [pipelines, setPipeline] = useState<Record<number, Pipeline>>({});

  const updatePipelines = async (pipelineId: string, pipeline: Pipeline) => {
    setPipeline((prevPipelines) => ({
      ...prevPipelines,
      [pipelineId]: pipeline,
    }));
  };

  return (
    <PipelineContext.Provider value={{ pipelines, updatePipelines }}>
      {children}
    </PipelineContext.Provider>
  );
};
