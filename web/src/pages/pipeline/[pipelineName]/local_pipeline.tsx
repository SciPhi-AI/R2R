import { useRouter } from 'next/router';
import { useEffect, useState } from 'react';
import Layout from '@/components/Layout';
import { Footer } from '@/components/Footer';
import { usePipelineContext } from '@/context/PipelineContext';

import { Link } from 'lucide-react';

import {
  CardTitle,
  CardDescription,
  CardHeader,
  CardContent,
  CardFooter,
  Card,
} from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

import { Separator } from '@/components/ui/separator';
import styles from '@/styles/Index.module.scss';

const PipelinePage = () => {
  const [pipelineToDelete, setPipelineToDelete] = useState('');
  const [deleteButtonDisabled, setDeleteButtonDisabled] = useState(true);
  const { pipelines, updatePipelines } = usePipelineContext();

  const router = useRouter();
  const { pipelineName } = router.query;
  console.log('pipelineName = ', pipelineName);
  const pipeline = pipelines[pipelineName as string];
  const pipelineId = pipeline?.id?.toString();

  useEffect(() => {
    const update = async () => {
      try {
        const response = await fetch(`/api/local_pipelines`, {
          headers: new Headers({
            'Content-Type': 'application/json',
          }),
        });
        const data = await response.json();
        for (const pipeline of data.pipelines) {
          updatePipelines(pipeline.id, pipeline);
        }
      } catch (error) {
        console.error('Error updating local pipeline:', error);
      }
    };

    update();
  }, [pipelineName]);

  console.log('pipeline = ', pipeline);
  if (pipeline) {
    console.log('pipelineId = ', pipeline.id);
    console.log('pipelineName= ', pipeline.name);
  } else {
    console.log('Pipeline data is not available');
  }

  const handleDeletePipeline = async () => {
    if (pipeline.id) {
      const response = await fetch(`/api/local_pipelines?id=${pipeline.id}`, {
        method: 'DELETE',
        headers: new Headers({
          'Content-Type': 'application/json',
        }),
      });

      if (response.ok) {
        updatePipelines(pipelineId, null);
        setPipelineToDelete('');
        setDeleteButtonDisabled(true);
        router.push('/');
      } else {
        console.error('Failed to delete pipeline');
      }
    } else {
      console.error('Pipeline not found');
    }
  };

  if (!pipeline) {
    // Handle the case where pipeline is null or render nothing or a loader
    return <div>Loading...</div>;
  }
  return (
    <Layout>
      <main className={styles.main}>
        {pipeline && (
          <h1 className="text-white text-2xl mb-4">
            Pipeline{' '}
            <code className="font-mono text-gray-500"> id:{pipeline.id}</code>
          </h1>
        )}
        <Separator />
        <Card className="my-6 w-full max-w-lg">
          <CardHeader className="pb-0">
            <CardTitle className="text-xl">{pipeline.name}</CardTitle>
            <CardDescription>
              This is a deployment of an immutable snapshot of RAG pipeline at a
              specific point in time.
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-0">
            <div className="grid gap-4">
              <div className="grid gap-2">
                <div className="flex items-center gap-2"></div>
                {pipeline.deployment && (
                  <div className="flex items-center gap-2">
                    <CalendarClockIcon className="w-4 h-4" />
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {pipeline.deployment?.create_time}
                    </span>
                  </div>
                )}
                {pipeline.deployment && (
                  <>
                    <Separator className="h-px" />
                    <div className="grid gap-2">
                      <div className="flex items-center gap-2 text-gray-500 dark:text-gray-400">
                        {'Last updated: ' + pipeline.deployment?.update_time}
                      </div>
                    </div>
                  </>
                )}
              </div>
            </div>
          </CardContent>
          <CardFooter>
            <div className="flex flex-col w-full gap-4">
              <div className="flex justify-between items-center">
                <div className="flex items-center gap-2">
                  {pipeline.status == 'finished' && (
                    <CheckCircleIcon className="w-4 h-4" />
                  )}
                  {pipeline.status}
                </div>
              </div>
              <Separator className="h-px" />
              <Label className="pl-1">Delete</Label>
              <div className="flex items-center -mt-2">
                <Input
                  type="text"
                  value={pipelineToDelete}
                  onChange={(e) => {
                    setPipelineToDelete(e.target.value);
                    setDeleteButtonDisabled(e.target.value !== pipeline.name);
                  }}
                  placeholder={`Enter pipeline name '${pipeline.name}' to enable delete.`}
                  className="flex-grow"
                  style={{
                    outline: 'none', // Removes the default outline
                    boxShadow: '0 0 2px #719ECE', // Sets a subtle glow, adjust as needed
                  }}
                />
                <button
                  className={`px-4 py-2 ml-2 text-white rounded ${
                    deleteButtonDisabled
                      ? 'bg-gray-400 cursor-not-allowed'
                      : 'bg-red-500 hover:bg-red-600'
                  }`}
                  onClick={handleDeletePipeline}
                  disabled={deleteButtonDisabled}
                >
                  Delete
                </button>
              </div>
            </div>
          </CardFooter>
        </Card>
      </main>

      <Footer />
    </Layout>
  );
};

function CalendarClockIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 7.5V6a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h3.5" />
      <path d="M16 2v4" />
      <path d="M8 2v4" />
      <path d="M3 10h5" />
      <path d="M17.5 17.5 16 16.25V14" />
      <path d="M22 16a6 6 0 1 1-12 0 6 6 0 0 1 12 0Z" />
    </svg>
  );
}

function CheckCircleIcon(props) {
  return (
    <svg
      {...props}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  );
}

export default PipelinePage;
