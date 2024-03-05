import styles from './styles.module.scss';
import React, { useState } from 'react';
import { createClient } from '@/utils/supabase/component';

export function CreatePipelineHeader() {
  // Initialize state with default values
  const [pipelineName, setPipelineName] = useState('');
  const [repoUrl, setRepoUrl] = useState('');

  const supabase = createClient();

  const createPipeline = async () => {
    // Assuming you have a function to get the current session token
    // This could be replaced with a context or global state retrieval
    const session = await supabase.auth.getSession();
    const token = session.data?.session?.access_token;
  
    const response = await fetch('/api/create_pipeline', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`, // Include the authorization header
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
  };

  return (
    <div className={styles.container}>
      {/* <label htmlFor="pipelineName" style={{color: 'white'}}>Pipeline Name</label> */}
      <input
        style={{color: 'black', borderRadius: '5px'}}
        value={pipelineName}
        placeholder="Pipeline Name"
        onChange={(e) => setPipelineName(e.target.value)}
      />
      {/* <label htmlFor="repoUrl" style={{color: 'white'}}>Github Repo URL</label> */}
      <input
        style={{color: 'black', borderRadius: '5px'}}
        value={repoUrl}
        placeholder="Github Repo URL"
        onChange={(e) => setRepoUrl(e.target.value)}
      />
      <button className={styles.newProjectButton} onClick={createPipeline}>New Pipeline</button>
    </div>
  );
}