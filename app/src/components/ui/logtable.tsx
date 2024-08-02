// eslint-disable-next-line @typescript-eslint/ban-ts-comment
// @ts-nocheck
import {
  ChevronDown,
  ChevronRight,
  ChevronLeft,
  ChevronRight as ChevronRightIcon,
} from 'lucide-react';
import React, { useState, useEffect } from 'react';

import { Button } from '@/components/ui/Button';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const COLLAPSIBLE_THRESHOLD = 100;
const LOGS_PER_PAGE = 5;

const LogTable = ({ logs }: { logs: LogType[] }) => {
  const [expandedCells, setExpandedCells] = useState({});
  const [currentPage, setCurrentPage] = useState(1);
  const [paginatedLogs, setPaginatedLogs] = useState([]);

  const toggleCell = (rowId: str) => {
    setExpandedCells((prev) => ({ ...prev, [rowId]: !prev[rowId] }));
  };

  const flattenedLogs = logs.flatMap((log) =>
    log.entries.map((entry, index) => ({
      id: `${log.run_id}-${index}`,
      run_id: log.run_id,
      run_type: log.run_type,
      key: entry.key,
      value: entry.value,
    }))
  );

  const groupedLogs = flattenedLogs.reduce((acc, log) => {
    if (!acc[log.run_id]) {
      acc[log.run_id] = [];
    }
    acc[log.run_id].push(log);
    return acc;
  }, {});

  const totalPages = Math.ceil(Object.keys(groupedLogs).length / LOGS_PER_PAGE);

  useEffect(() => {
    const startIndex = (currentPage - 1) * LOGS_PER_PAGE;
    const endIndex = startIndex + LOGS_PER_PAGE;
    const paginatedEntries = Object.entries(groupedLogs).slice(
      startIndex,
      endIndex
    );
    setPaginatedLogs(
      paginatedEntries.map(([runId, logs]) => ({ runId, logs }))
    );
  }, [currentPage, logs]);

  const truncateValue = (value, maxLength = 50) => {
    if (typeof value === 'string' && value.length > maxLength) {
      return value.substring(0, maxLength) + '...';
    }
    return value;
  };

  const prettifyJSON = (value, indent = 0) => {
    if (typeof value !== 'string') {
      return value;
    }

    try {
      const outerArray = JSON.parse(value);
      const parsedArray = outerArray.map((item) => {
        if (typeof item === 'string') {
          try {
            return JSON.parse(item);
          } catch (e) {
            return item;
          }
        }
        return item;
      });

      return formatObject(parsedArray, indent);
    } catch (e) {
      return value;
    }
  };

  const formatObject = (obj, indent = 0) => {
    if (typeof obj !== 'object' || obj === null) {
      return JSON.stringify(obj);
    }

    const isArray = Array.isArray(obj);
    const brackets = isArray ? ['[', ']'] : ['{', '}'];
    const indentStr = '  '.repeat(indent);
    const nextIndentStr = '  '.repeat(indent + 1);

    const formatted = Object.entries(obj)
      .map(([key, value]) => {
        const formattedValue = formatObject(value, indent + 1);
        return isArray
          ? `${nextIndentStr}${formattedValue}`
          : `${nextIndentStr}"${key}": ${formattedValue}`;
      })
      .join(',\n');

    return `${brackets[0]}\n${formatted}\n${indentStr}${brackets[1]}`;
  };

  const renderValue = (log) => {
    const isCollapsible =
      typeof log.value === 'string' && log.value.length > COLLAPSIBLE_THRESHOLD;
    const prettyValue = prettifyJSON(log.value);

    if (isCollapsible) {
      return (
        <Collapsible open={expandedCells[log.id]}>
          <CollapsibleTrigger
            onClick={() => toggleCell(log.id)}
            className="flex items-center w-full text-left"
          >
            {expandedCells[log.id] ? (
              <ChevronDown className="mr-2 flex-shrink-0" />
            ) : (
              <ChevronRight className="mr-2 flex-shrink-0" />
            )}
            <span className="truncate">{truncateValue(prettyValue)}</span>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <pre className="mt-2 whitespace-pre-wrap overflow-x-auto text-xs">
              {prettyValue}
            </pre>
          </CollapsibleContent>
        </Collapsible>
      );
    } else {
      return (
        <pre className="whitespace-pre-wrap overflow-x-auto text-xs">
          {prettyValue}
        </pre>
      );
    }
  };

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-1/6">Run ID</TableHead>
            <TableHead className="w-1/6">Run Type</TableHead>
            <TableHead className="w-1/6">Key</TableHead>
            <TableHead className="w-1/2">Value</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {paginatedLogs.map(({ runId, logs }) => (
            <React.Fragment key={runId}>
              <TableRow className="bg-muted/50">
                <TableCell colSpan={4} className="font-semibold">
                  Run ID: {runId} ({logs[0].run_type})
                </TableCell>
              </TableRow>
              {logs.map((log) => (
                <TableRow key={log.id} className="align-top">
                  <TableCell className="w-1/6"></TableCell>
                  <TableCell className="w-1/6"></TableCell>
                  <TableCell className="w-1/6 pt-3">{log.key}</TableCell>
                  <TableCell className="w-1/2">{renderValue(log)}</TableCell>
                </TableRow>
              ))}
            </React.Fragment>
          ))}
        </TableBody>
      </Table>
      <div className="flex items-center justify-end space-x-2 py-4">
        <Button
          variant="outline"
          onClick={() => setCurrentPage((page) => Math.max(1, page - 1))}
          disabled={currentPage === 1}
        >
          <ChevronLeft className="h-4 w-4" />
          Previous
        </Button>
        <div className="text-sm font-medium">
          Page {currentPage} of {totalPages}
        </div>
        <Button
          variant="outline"
          onClick={() =>
            setCurrentPage((page) => Math.min(totalPages, page + 1))
          }
          disabled={currentPage === totalPages}
        >
          Next
          <ChevronRightIcon className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};

export default LogTable;
