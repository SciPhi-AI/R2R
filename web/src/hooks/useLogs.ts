import { useState, useEffect, useCallback } from 'react';

import { EventSummary } from '../types'; // Adjust the import path as needed

const useLogs = () => {
  const [logs, setLogs] = useState<EventSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);
  
  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/logs_summary');
      if (!response.ok) {
        throw new Error('Network response was not ok');
      }
      const data = await response.json();
      const logs = data.events_summary.map((event: EventSummary) => {
        console.log('event', event);
        // TODO: Update with actual score and consume from API
        // Generate a score for each log entry with a successful outcome
        const score =
          event.searchResults !== undefined && event.searchResults.length > 0
            ? Number(event.searchResults[0].score).toFixed(2)
            : '';
        return {
          timestamp: event.timestamp,
          pipelineRunId: event.pipelineRunId,
          pipelineRunType: event.pipelineRunType,
          method: event.method,
          evalResults: event.evalResults,
          searchQuery: event.searchQuery,
          searchResults: event.searchResults,
          embeddingChunks: event.embeddingChunks,
          document: event.document,
          completionResult: event.completionResult,
          outcome: event.outcome,
          score,
        };
      });
      setLogs(logs);
    } catch (error) {
      if (error instanceof Error) {
        setError(error);
      } else {
        setError(new Error('An unknown error occurred'));
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);



  return { logs, loading, error, refetch: fetchLogs };
};

export default useLogs;
