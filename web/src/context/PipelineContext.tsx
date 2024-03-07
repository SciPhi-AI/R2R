import { createContext, useContext, useState, useEffect } from 'react';
import { Pipeline } from '../types'; // Import the Pipeline type
import { useAuth } from './authProvider';

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
  const { cloudMode } = useAuth();

  const updatePipelines = async (pipelineId: string, pipeline: Pipeline) => {
    // if (cloudMode === 'cloud') {
    setPipeline((prevPipelines) => ({
      ...prevPipelines,
      [pipelineId]: pipeline,
    }));
    // }

    // if (cloudMode === 'local') {
    //   const response = await fetch('/api/local_pipelines', {
    //     method: 'POST',
    //     headers: {
    //       'Content-Type': 'application/json',
    //     },
    //     body: JSON.stringify({ id: pipelineId, pipeline }),
    //   });

    //   if (response.ok) {
    //     // Update local state if necessary
    //     setPipeline((prevPipelines) => ({
    //       ...prevPipelines,
    //       [pipelineId]: pipeline,
    //     }));
    //   } else {
    //     // Handle error
    //     console.error('Failed to update pipeline');
    //   }
    // }
  };

  return (
    <PipelineContext.Provider value={{ pipelines, updatePipelines }}>
      {children}
    </PipelineContext.Provider>
  );
};
