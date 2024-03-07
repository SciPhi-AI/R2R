import { useCallback } from 'react';
import { usePipelineContext } from '@/context/PipelineContext';
import { Pipeline } from '../types';

export const useUpdatePipelineProp = <T extends keyof Pipeline>() => {
  const { updatePipelineProp } = usePipelineContext();

  const updateProp = useCallback(
    (propName: T, propValue: Pipeline[T]) => {
      updatePipelineProp(propName, propValue);
    },
    [updatePipelineProp]
  );

  return updateProp;
};
