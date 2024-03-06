import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
// Grouped and organized imports
import { createClient } from '@/utils/supabase/component';
import { useAuth } from '@/context/authProvider';
import { usePipelineContext } from '@/context/PipelineContext';
import { useUpdatePipelineProp } from '@/hooks/useUpdatePipelineProp';
import styles from './styles.module.scss';

// New type for pipeline details
interface PipelineDetails {
  name: string;
  repoUrl?: string;
  localEndpoint: string;
}

interface CreatePipelineHeaderProps {
  onAddPipeline: (newPipeline: PipelineDetails) => void;
}

export const CreatePipelineHeader: React.FC<CreatePipelineHeaderProps> = ({
  onAddPipeline,
}) => {
  const router = useRouter();
  const { pipeline } = usePipelineContext();
  const [isUpdateComplete, setIsUpdateComplete] = useState(false);
  const updatePipelineProp = useUpdatePipelineProp();
  const supabase = createClient();
  const { cloudMode } = useAuth();

  // Combined state
  const [pipelineDetails, setPipelineDetails] = useState<PipelineDetails>({
    name: '',
    repoUrl: '',
    localEndpoint: 'http://localhost:8000',
  });

  useEffect(() => {
    if (isUpdateComplete && pipeline?.id) {
      console.log('Pipeline updated with id:', pipeline.id);
      router.push(`/pipeline/${pipeline.id}`);
    }
  }, [isUpdateComplete, pipeline, router]);

  const createPipeline = async () => {
    if (cloudMode === 'cloud') {
      const session = await supabase.auth.getSession();
      const token = session.data?.session?.access_token;
      // Extracted API call logic
      try {
        const pipelineId = await createCloudPipeline(pipelineDetails, token);
        router.push(`/pipeline/${pipelineId}`);
      } catch (error) {
        console.error('Failed to create pipeline', error);
        // Ideally, show an error message to the user
      }
    } else {
      // Local pipeline creation logic remains the same
      const pipelineId = Math.floor(Math.random() * 100000) + 1;
      updatePipelineProp('id', pipelineId);
      setIsUpdateComplete(true);
    }
  };

  // Handling input changes in a single function
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setPipelineDetails((prevDetails) => ({ ...prevDetails, [name]: value }));
  };

  return (
    <div className={styles.container}>
      <input
        name="name"
        style={{ color: 'black', borderRadius: '5px' }}
        value={pipelineDetails.name}
        placeholder="Pipeline Name"
        onChange={handleInputChange}
      />
      {cloudMode === 'cloud' && (
        <input
          name="repoUrl"
          style={{ color: 'black', borderRadius: '5px' }}
          value={pipelineDetails.repoUrl}
          placeholder="Github Repo URL"
          onChange={handleInputChange}
        />
      )}
      <input
        name="localEndpoint"
        style={{ color: 'black', borderRadius: '5px' }}
        value={pipelineDetails.localEndpoint}
        placeholder="Localhost Endpoint"
        onChange={handleInputChange}
      />
      <button className={styles.newProjectButton} onClick={createPipeline}>
        New Pipeline
      </button>
    </div>
  );
};

async function createCloudPipeline(
  details: PipelineDetails,
  token: string
): Promise<string> {
  const response = await fetch('/api/create_pipeline', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      pipeline_name: details.name,
      repo_url: details.repoUrl,
    }),
  });

  if (!response.ok) {
    throw new Error('Failed to create pipeline');
  }

  const data = await response.json();
  return data.id;
}
