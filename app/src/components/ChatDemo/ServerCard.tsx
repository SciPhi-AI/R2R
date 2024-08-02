import { Link, Check, ClipboardCheck } from 'lucide-react';
import React, { useState } from 'react';

import {
  PipelineStatus,
  useConnectionStatus,
} from '@/components/ChatDemo/PipelineStatus';
import { formatUptime } from '@/components/ChatDemo/utils/formatUptime';
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from '@/components/ui/card';
import { R2RServerCardProps } from '@/types';

const R2RServerCard: React.FC<R2RServerCardProps> = ({
  pipeline,
  onStatusChange,
}) => {
  const [copied, setCopied] = useState(false);
  const { isConnected, serverStats, localUptime } = useConnectionStatus(
    pipeline?.deploymentUrl,
    onStatusChange
  );

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text).then(
      () => {
        setCopied(true);
        setTimeout(() => setCopied(false), 2000);
      },
      (err) => console.error('Failed to copy text: ', err)
    );
  };

  return (
    <Card className="h-full flex flex-col">
      <CardHeader className="pb-0">
        <CardTitle className="text-xl">R2R Server</CardTitle>
        <PipelineStatus onStatusChange={onStatusChange} />
        <CardDescription>Your deployment of an R2R server.</CardDescription>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid gap-4">
          <div className="mt-4">
            <h3 className="text-lg font-semibold">Deployment Status</h3>
            <div className="grid grid-cols-2 gap-2 text-sm">
              <div>
                <p className="font-medium">Uptime:</p>
                <p>{isConnected ? formatUptime(localUptime) : 'N/A'}</p>
              </div>
              <div>
                <p className="font-medium">CPU Usage:</p>
                <p>
                  {serverStats ? `${serverStats.cpu_usage.toFixed(1)}%` : 'N/A'}
                </p>
              </div>
              <div>
                <p className="font-medium">Start Time:</p>
                <p>
                  {serverStats
                    ? new Date(serverStats.start_time).toLocaleString()
                    : 'N/A'}
                </p>
              </div>
              <div>
                <p className="font-medium">Memory Usage:</p>
                <p>
                  {serverStats
                    ? `${serverStats.memory_usage.toFixed(1)}%`
                    : 'N/A'}
                </p>
              </div>
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 pt-4">
          <Link width="20" height="20" />
          <span className="text-sm text-gray-500 dark:text-gray-400">
            {pipeline?.deploymentUrl}
          </span>
          {copied ? (
            <Check className="w-4 h-4" />
          ) : (
            <ClipboardCheck
              className="w-4 h-4 cursor-pointer"
              onClick={() => handleCopy(pipeline?.deploymentUrl || '')}
            />
          )}
        </div>
      </CardContent>
    </Card>
  );
};

export default R2RServerCard;
