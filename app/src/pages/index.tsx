import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from 'chart.js';
import {
  Check,
  ClipboardCheck,
  Link,
  BookOpenText,
  FileText,
  MessageCircle,
  BarChart2,
  FileSearch,
  Users,
} from 'lucide-react';
import Image from 'next/image';
import { useRouter } from 'next/router';
import { useState, useEffect } from 'react';
import { Line } from 'react-chartjs-2';

import { PipelineStatus } from '@/components/ChatDemo/PipelineStatus';
import R2RServerCard from '@/components/ChatDemo/ServerCard';
import Layout from '@/components/Layout';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/Button';
import {
  CardTitle,
  CardDescription,
  CardHeader,
  CardContent,
  Card,
} from '@/components/ui/card';
import { useUserContext } from '@/context/UserContext';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

const HomePage = () => {
  const router = useRouter();
  const { isAuthenticated, pipeline } = useUserContext();
  const [copied, setCopied] = useState(false);
  const [isConnected, setIsConnected] = useState(false);

  // const chartData = {
  //   labels: ['Day 1', 'Day 2', 'Day 3', 'Day 4', 'Day 5', 'Day 6', 'Day 7'],
  //   datasets: [
  //     {
  //       label: 'Requests per Day',
  //       data: [120, 190, 300, 500, 800, 1200, 2000],
  //       fill: false,
  //       borderColor: 'rgb(59, 130, 246)',
  //       backgroundColor: 'rgb(59, 130, 246)',
  //       tension: 0.1,
  //     },
  //   ],
  // };

  // const chartOptions = {
  //   responsive: true,
  //   plugins: {
  //     legend: {
  //       position: 'top',
  //     },
  //     title: {
  //       display: true,
  //       text: 'Requests Growth',
  //     },
  //   },
  //   scales: {
  //     y: {
  //       beginAtZero: true,
  //       title: {
  //         display: true,
  //         text: 'Number of Requests',
  //       },
  //     },
  //     x: {
  //       title: {
  //         display: true,
  //         text: 'Day',
  //       },
  //     },
  //   },
  // };

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/login');
    }
  }, [isAuthenticated, router]);

  if (!isAuthenticated) {
    return null;
  }

  const handleCopy = (text: string) => {
    if (!navigator.clipboard) {
      const textarea = document.createElement('textarea');
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      try {
        document.execCommand('copy');
      } catch (err) {
        console.error('Failed to copy text: ', err);
      }
      document.body.removeChild(textarea);
    } else {
      navigator.clipboard.writeText(text).then(
        () => {},
        (err) => {
          console.error('Failed to copy text: ', err);
        }
      );
    }
  };

  return (
    <Layout isConnected={isConnected}>
      <main className="w-full flex flex-col min-h-screen mt-[4rem] sm:mt-[6rem] container mb-[4rem] sm:mb-[6rem]">
        <div className="flex flex-col lg:flex-row gap-4">
          {/* Left column - Alert */}
          <div className="w-full lg:w-2/3 flex flex-col gap-4">
            <Alert variant="default" className="h-full flex flex-col">
              <AlertTitle className="text-lg ">
                <div className="flex gap-2 text-xl">
                  <span className="text-gray-500 dark:text-gray-200 font-semibold">
                    You're connected to your R2R deployment!
                  </span>
                </div>
              </AlertTitle>
              <AlertDescription>
                <p className="mb-4 text-sm text-gray-600 dark:text-gray-300">
                  Here, you'll find a number of tools to help you manage your
                  pipelines and deploy user-facing applications directly to
                  users.
                </p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
                  <div className="flex items-start space-x-3">
                    <FileText className="w-5 h-5 text-primary" />
                    <div>
                      <h3 className="text-sm font-semibold mb-1">Documents</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Upload, update, and delete documents and their metadata.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <MessageCircle className="w-5 h-5 text-primary" />
                    <div>
                      <h3 className="text-sm font-semibold mb-1">Chat</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Stream RAG and knowledge graph responses with different
                        models and configurable settings.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <Users className="w-5 h-5 text-primary" />
                    <div>
                      <h3 className="text-sm font-semibold mb-1">Users</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Track user queries, search results, and LLM responses.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <FileSearch className="w-5 h-5 text-primary" />
                    <div>
                      <h3 className="text-sm font-semibold mb-1">Logs</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        Track user queries, search results, and LLM responses.
                      </p>
                    </div>
                  </div>
                  <div className="flex items-start space-x-3">
                    <BarChart2 className="w-5 h-5 text-primary" />
                    <div>
                      <h3 className="text-sm font-semibold mb-1">Analytics</h3>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        View aggregate statistics around latencies and metrics
                        with detailed histograms.
                      </p>
                    </div>
                  </div>
                </div>
                <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">
                    Have a feature request or found a bug? Create a Github issue
                    and help us improve the R2R dashboard!
                  </p>
                  <div className="flex space-x-4">
                    <Button
                      className="flex items-center justify-center px-4 py-2 text-sm"
                      variant="light"
                      onClick={() =>
                        window.open(
                          'https://github.com/SciPhi-AI/R2R-Dashboard/issues/new?assignees=&labels=&projects=&template=feature_request.md&title=',
                          '_blank'
                        )
                      }
                    >
                      Feature Request
                    </Button>
                    <Button
                      className="flex items-center justify-center px-4 py-2 text-sm"
                      variant="light"
                      onClick={() =>
                        window.open(
                          'https://github.com/SciPhi-AI/R2R-Dashboard/issues/new?assignees=&labels=&projects=&template=bug_report.md&title=',
                          '_blank'
                        )
                      }
                    >
                      Report a Bug
                    </Button>
                  </div>
                </div>
              </AlertDescription>
            </Alert>
            {/* SDK Cards */}
            <div className="flex flex-col gap-4">
              <h2 className="text-xl font-semibold mb-2">SDKs</h2>
              <div className="flex flex-col sm:flex-row gap-4">
                <Card className="w-full sm:w-1/2 flex flex-col">
                  <CardHeader className="flex flex-row items-center space-x-2">
                    <Image
                      src="/images/python-logo.svg"
                      alt="Python Logo"
                      width={30}
                      height={30}
                    />
                    <CardTitle>Python SDK</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col justify-end flex-grow">
                    <div className="flex flex-row space-x-2">
                      <Button
                        className="rounded-md py-1 px-3"
                        variant="light"
                        onClick={() =>
                          window.open(
                            'https://r2r-docs.sciphi.ai/walkthrough',
                            '_blank'
                          )
                        }
                      >
                        <div className="flex items-center">
                          <BookOpenText size={20} className="mr-2" />
                          <span>Docs</span>
                        </div>
                      </Button>
                      <Button
                        className="rounded-md py-1 px-3"
                        variant="light"
                        onClick={() =>
                          window.open(
                            'https://github.com/SciPhi-AI/R2R',
                            '_blank'
                          )
                        }
                      >
                        <div className="flex items-center">
                          <Image
                            src="/images/github-mark.svg"
                            alt="GitHub Logo"
                            width={20}
                            height={20}
                            className="mr-2"
                          />
                          <span>View on GitHub</span>
                        </div>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
                <Card className="w-full sm:w-1/2 flex flex-col">
                  <CardHeader className="flex flex-row items-center space-x-2">
                    <Image
                      src="/images/javascript-logo.svg"
                      alt="JavaScript Logo"
                      width={30}
                      height={30}
                    />
                    <CardTitle>JavaScript SDK</CardTitle>
                  </CardHeader>
                  <CardContent className="flex flex-col justify-end flex-grow">
                    <div className="flex flex-row space-x-2">
                      <Button
                        className="rounded-md py-1 px-3"
                        variant="light"
                        onClick={() =>
                          window.open(
                            'https://r2r-docs.sciphi.ai/cookbooks/web-dev',
                            '_blank'
                          )
                        }
                      >
                        <div className="flex items-center">
                          <BookOpenText size={20} className="mr-2" />
                          <span>Docs</span>
                        </div>
                      </Button>
                      <Button
                        className="rounded-md py-1 px-3"
                        variant="light"
                        onClick={() =>
                          window.open(
                            'https://github.com/SciPhi-AI/r2r-js',
                            '_blank'
                          )
                        }
                      >
                        <div className="flex items-center">
                          <Image
                            src="/images/github-mark.svg"
                            alt="GitHub Logo"
                            width={20}
                            height={20}
                            className="mr-2"
                          />
                          <span>View on GitHub</span>
                        </div>
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            </div>
          </div>

          {/* Right column - Cards */}
          <div className="w-full lg:w-1/3 flex flex-col gap-4">
            {/* R2R Server Cards */}
            <div className="flex flex-col gap-4">
              {pipeline && (
                <R2RServerCard
                  pipeline={pipeline}
                  onStatusChange={setIsConnected}
                />
              )}

              {/* <Card className="h-full flex flex-col">
                <CardHeader className="pb-0">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-xl">Requests</CardTitle>
                  </div>
                  <CardDescription>
                    Requests to your R2R server over the past week.
                  </CardDescription>
                </CardHeader>
                <CardContent className="pt-0">
                  <div className="mt-4 h-64">
                    <Line data={chartData} options={chartOptions} />
                  </div>
                </CardContent>
              </Card> */}
            </div>
          </div>
        </div>
      </main>
    </Layout>
  );
};

export default HomePage;
