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
import styles from '@/styles/Index.module.scss';

const LocalDeploy = () => {
  const [pipelineName, setPipelineName] = useState('');
  const [localEndpoint, setLocalEndpoint] = useState('localhost:8000');
  const [isLoading, setIsLoading] = useState(false);

  const router = useRouter();

  const handleSubmit = async () => {
    setIsLoading(true);

    // Ensure the URL includes the HTTP scheme
    const fullEndpointUrl = `http://${localEndpoint}/logs`;

    // Attempt to fetch logs from the local endpoint to verify it's working
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

      const logsData = await logsResponse.json();
      if (logsData.length === 0) {
        alert(
          'The local endpoint is working, but there are no logs. Ensure the system is correctly initialized.'
        );
      } else {
        // If there are logs, it means the endpoint is definitely working
        alert('The local endpoint is working and logs are present.');
      }

      // Since the goal is to verify the endpoint, navigate to /success if the endpoint is responsive
      router.push('/success');
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
