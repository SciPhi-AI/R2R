import { useState, useEffect } from 'react';

import { EventSummary } from '../types'; // Adjust the import path as needed

const useLogs = () => {
  const [logs, setLogs] = useState<EventSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    const fetchLogs = async () => {
      try {
        const response = await fetch('/api/logs_summary');
        if (!response.ok) {
          throw new Error('Network response was not ok');
        }
        const data = await response.json();
        const logs = data.events_summary.map((event: EventSummary) => {
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
    };

    fetchLogs();
  }, []);

  return { logs, loading, error };
};

export default useLogs;
