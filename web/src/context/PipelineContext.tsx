import { createContext, useContext, useState } from 'react';
import { Pipeline } from '../types'; // Import the Pipeline type
import { useRouter } from 'next/router';

interface PipelineContextProps {
  pipeline: Pipeline | null; // Use the Pipeline type for the context
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
  deployment: {
    id: 4242,
    uri: 'https://example.uri.com',
  },
};

const PipelineContext = createContext<PipelineContextProps>({
  pipeline: defaultPipeline,
  updatePipelineProp: () => {},
  navigateToPipeline: () => {},
});

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
