import { useState } from 'react';
import { useRouter } from 'next/router';
import Layout from '@/components/Layout';
import {
  Card,
  CardHeader,
  CardContent,
  CardFooter,
} from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { usePipelineContext } from '@/context/PipelineContext';
import styles from '@/styles/Index.module.scss';

const LocalDeploy = () => {
  const [pipelineName, setPipelineName] = useState('');
  const [localEndpoint, setLocalEndpoint] = useState('localhost:8000');
  const [isLoading, setIsLoading] = useState(false);
  const router = useRouter();

  const generateUniqueId = (name: string, seed = 42) => {
    // Remove invalid characters and spaces, then add a random string
    const cleanName = name.replace(/[^a-zA-Z0-9]/g, '').toLowerCase();
    const seededRandomString = (Math.random() * seed)
      .toString(36)
      .substring(0, 8);
    return `${cleanName}-${seededRandomString}`;
  };

  // Create a random seed
  const seed = Math.floor(Math.random() * 1000);
  const uniqueId = generateUniqueId(pipelineName, seed);

  const handleSubmit = async () => {
    setIsLoading(true);

    // Ensure the URL includes the HTTP scheme
    const fullEndpointUrl = `http://${localEndpoint}/logs`;

    try {
      const logsResponse = await fetch(fullEndpointUrl, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
        },
      });

      if (!logsResponse.ok) {
        throw new Error(
          'Failed to connect to the local endpoint. Please check if it is running correctly.'
        );
      }

      // fetch pipelines array
      const response = await fetch('api/local_pipelines');
      const data = await response.json();
      const pipelines = data.pipelines || [];
      console.log('pipelines = ', pipelines);
      // Assuming verification is successful, create a new pipeline object
      const newPipeline = {
        id: uniqueId,
        name: pipelineName,
        endpoint: localEndpoint,
        github_url: 'https://github.com/example',
        status: 'active',
        deployment: {
          id: uniqueId, // Ensuring both IDs are the same
          uri: 'local',
          create_time: new Date().toISOString(),
          update_time: new Date().toISOString(),
          creator: 'exampleCreator',
          generation: '1',
          last_modifier: 'exampleModifier',
          uid: 'exampleUID',
          name: 'Local Deployment',
        },
      };

      // POST request to update the pipeline in the store
      await fetch('/api/local_pipelines', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          id: pipelineName, // Use pipelineName as the unique identifier
          pipeline: newPipeline,
        }),
      });

      alert('The local endpoint is working and the pipeline has been created.');
      router.push(`/pipeline/${pipelineName}/local_pipeline`);
    } catch (error) {
      console.error('Error:', error);
      alert(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Layout>
      <main className={styles.main}>
        <Card>
          <CardHeader>
            <h1 className="text-2xl font-bold">Create Local Pipeline</h1>
          </CardHeader>
          <CardContent>
            <div className="flex justify-between space-x-4">
              <div className="flex-1">
                <div className="flex flex-col items-start">
                  <Label htmlFor="pipeline-name" className="mb-3 px-1">
                    Pipeline Name
                  </Label>
                  <Input
                    id="pipeline-name"
                    placeholder="Enter the pipeline name"
                    className="w-full"
                    onChange={(e) => setPipelineName(e.target.value)}
                    value={pipelineName}
                  />
                </div>
              </div>
              <div className="flex-1">
                <div className="flex flex-col items-start">
                  <Label htmlFor="local-endpoint" className="mb-3 px-1">
                    Local Endpoint URL
                  </Label>
                  <Input
                    id="local-endpoint"
                    placeholder="Enter the local endpoint URL"
                    className="w-full"
                    onChange={(e) => setLocalEndpoint(e.target.value)}
                    value={localEndpoint}
                  />
                </div>
              </div>
            </div>
          </CardContent>
          <CardFooter className="flex justify-end">
            <button
              className={`bg-green-500 hover:bg-green-700 text-white font-bold py-2 px-4 rounded ${isLoading ? 'opacity-50' : ''}`}
              onClick={handleSubmit}
              disabled={isLoading}
            >
              Create
            </button>
          </CardFooter>
        </Card>
      </main>
    </Layout>
  );
};

export default LocalDeploy;
