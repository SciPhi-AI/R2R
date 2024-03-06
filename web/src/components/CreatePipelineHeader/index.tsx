import React, { useEffect, useState } from 'react';
import { createClient } from '@/utils/supabase/component';
import { useAuth } from '@/context/authProvider';
import { useRouter } from 'next/router';
import { usePipelineContext } from '@/context/PipelineContext';
import { useUpdatePipelineProp } from '@/hooks/useUpdatePipelineProp';
import { Pipeline } from '@/types';

import styles from './styles.module.scss';

interface CreatePipelineHeaderProps {
  onAddPipeline: (newPipeline: any) => void; // Adjust the type of newPipeline as needed
}

export const CreatePipelineHeader: React.FC<CreatePipelineHeaderProps> = ({
  onAddPipeline,
}) => {
  const router = useRouter();
  const { pipeline } = usePipelineContext();
  const [isUpdateComplete, setIsUpdateComplete] = useState(false);
  const updatePipelineProp = useUpdatePipelineProp(); // Moved to the top level

  // Initialize state with default values
  const [pipelineName, setPipelineName] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [localEndpoint, setLocalEndpoint] = useState('http://localhost:8000');

  const supabase = createClient();
  const { cloudMode } = useAuth();

  useEffect(() => {
    if (isUpdateComplete && pipeline && pipeline.id) {
      console.log('Pipeline updated with id:', pipeline.id);
      console.log('Pipeline Name:', pipeline.name);
      console.log('Pipeline Endpoint:', pipeline.deployment_url);
      console.log('Going to pipeline:', `/pipeline/${pipeline.id}`);

      // Perform the navigation after logging
      router.push(`/pipeline/${pipeline.id}`);
    }
  }, [isUpdateComplete, pipeline, router]);

  const createPipeline = async () => {
    // Add this line to get the setPipelineId function from the context
    if (cloudMode === 'cloud') {
      // Assuming you have a function to get the current session token
      // This could be replaced with a context or global state retrieval
      const session = await supabase.auth.getSession();
      const token = session.data?.session?.access_token;

      const response = await fetch('/api/create_pipeline', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`, // Include the authorization header
        },
        body: JSON.stringify({
          pipeline_name: pipelineName,
          repo_url: repoUrl,
        }),
      });

      if (!response.ok) {
        // Handle error
        console.error('Failed to create pipeline');
        return;
      }

      // Handle success
      const data = await response.json();
      const pipelineId = data.id;
      router.push(`/pipeline/${pipelineId}`);
    } else {
      // Create a local pipeline
      console.log('Creating a local pipeline with endpoint:', localEndpoint);
      const pipelineId = Math.floor(Math.random() * 100000) + 1;

      // Update pipeline properties
      updatePipelineProp('id', pipelineId);
      updatePipelineProp('name', pipelineName);
      updatePipelineProp('deployment_url', localEndpoint);
      updatePipelineProp('github_url', null); // Assuming 'null' is an acceptable value for this property
      updatePipelineProp('status', 'running');

      setIsUpdateComplete(true); // Indicate that update is complete
    }
  };

  return (
    <div className={styles.container}>
      {/* <label htmlFor="pipelineName" style={{color: 'white'}}>Pipeline Name</label> */}
      <input
        style={{ color: 'black', borderRadius: '5px' }}
        value={pipelineName}
        placeholder="Pipeline Name"
        onChange={(e) => setPipelineName(e.target.value)}
      />
      {/* <label htmlFor="repoUrl" style={{color: 'white'}}>Github Repo URL</label> */}
      {cloudMode === 'cloud' ? (
        <input
          style={{ color: 'black', borderRadius: '5px' }}
          value={repoUrl}
          placeholder="Github Repo URL"
          onChange={(e) => setRepoUrl(e.target.value)}
        />
      ) : (
        <input
          style={{ color: 'black', borderRadius: '5px' }}
          value={localEndpoint}
          placeholder="Localhost Endpoint"
          onChange={(e) => setLocalEndpoint(e.target.value)}
        />
      )}
      <button className={styles.newProjectButton} onClick={createPipeline}>
        New Pipeline
      </button>
    </div>
  );
};
