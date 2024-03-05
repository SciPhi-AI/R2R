import styles from './styles.module.scss';
import React, { useState } from 'react';
import { createClient } from '@/utils/supabase/component';

export function ProjectHeader() {
  // Initialize state with default values
  const [pipelineName, setPipelineName] = useState('test1');
  const [repoUrl, setRepoUrl] = useState('git@github.com:SciPhi-AI/R2R.git');

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
    console.log('Pipeline created:', data);
  };

  return (
    <div className={styles.container}>
      <input
        style={{color: 'black'}}
        value={pipelineName}
        onChange={(e) => setPipelineName(e.target.value)}
        // placeholder="Pipeline Name"
      />
      <input
        style={{color: 'black'}}
        value={repoUrl}
        onChange={(e) => setRepoUrl(e.target.value)}
        // placeholder="Repository URL"
      />
      <button className={styles.newProjectButton} onClick={createPipeline}>New Pipeline</button>
    </div>
  );
}