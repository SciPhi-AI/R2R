import styles from './styles.module.scss';
import React, { useState } from 'react';
import { createClient } from '@/utils/supabase/component';
import { useRouter } from 'next/router';

export function CreatePipelineHeader({numPipelines}: {numPipelines: number}) {
  // // Initialize state with default values
  // const [pipelineName, setPipelineName] = useState('');
  // const [repoUrl, setRepoUrl] = useState('');

  // const supabase = createClient();

  // const createPipeline = async () => {
  //   // Assuming you have a function to get the current session token
  //   // This could be replaced with a context or global state retrieval
  //   const session = await supabase.auth.getSession();
  //   const token = session.data?.session?.access_token;
  
  //   const response = await fetch('/api/create_pipeline', {
  //     method: 'POST',
  //     headers: {
  //       'Content-Type': 'application/json',
  //       'Authorization': `Bearer ${token}`, // Include the authorization header
  //     },
  //     body: JSON.stringify({
  //       pipeline_name: pipelineName,
  //       repo_url: repoUrl,
  //     }),
  //   });
  
  //   if (!response.ok) {
  //     // Handle error
  //     console.error('Failed to create pipeline');
  //     return;
  //   }
  
  //   // Handle success
  //   const data = await response.json();
  // };
  const router = useRouter(); // Initialize the router

  const createPipeline = async () => {
    router.push('/deploy');
  }

  return (
    <div className={styles.container}>
      <button className={styles.newProjectButton} onClick={createPipeline}>New Pipeline</button>
      <span style={{fontWeight: 'bold', marginLeft: '5px', marginTop:"10px"}}>{numPipelines}/10 pipelines deployed</span>

    </div>
  );
}