import React, { useState, useMemo } from 'react';

import Highlight from '@/components/ui/highlight';
import Pagination from '@/components/ui/pagination';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { setColor, setTextColor } from '@/lib/utils';

type Log = {
  timestamp: string;
  severity: string;
  payload: string;
};

const LogTable = ({ logs, loading }: { logs: Log[]; loading: boolean }) => {
  const [sortField, setSortField] = useState<keyof Log>('timestamp');
  const [sortDirection, setSortDirection] = useState('desc');
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  const isLoading = loading;

  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentItems = (logs || []).slice(indexOfFirstItem, indexOfLastItem);

  const paginate = (pageNumber: number) => setCurrentPage(pageNumber);

  const sortedLogs = useMemo(() => {
    return [...currentItems].sort((a, b) => {
      if (a[sortField as keyof Log] < b[sortField as keyof Log]) {
        return sortDirection === 'asc' ? -1 : 1;
      }
      if (a[sortField as keyof Log] > b[sortField as keyof Log]) {
        return sortDirection === 'asc' ? 1 : -1;
      }
      return 0;
    });
  }, [currentItems, sortField, sortDirection]);

  return (
    <div className="min-h-screen w-full">
      <div className="flex flex-col">
        <main className="flex flex-1 flex-col gap-4 md:gap-8 mb-4">
          <header className="bg-zinc-800 py-2 px-6 rounded-t-lg">
            <h3 className="text-xl font-bold">Server Logs</h3>
          </header>
          <div className="border shadow-sm rounded-lg w-full">
            {isLoading ? (
              <div className="flex items-center justify-center p-2">
                <p className="text-center text-gray-700 dark:text-gray-300">
                  Loading Logs...
                </p>
                <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-gray-900"></div>
              </div>
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead
                        className="w-[200px]"
                        onClick={() => {
                          setSortField('timestamp');
                          setSortDirection(
                            sortDirection === 'asc' ? 'desc' : 'asc'
                          );
                        }}
                      >
                        Timestamp
                      </TableHead>
                      <TableHead
                        className="w-[100px]"
                        onClick={() => {
                          setSortField('severity');
                          setSortDirection(
                            sortDirection === 'asc' ? 'desc' : 'asc'
                          );
                        }}
                      >
                        Severity
                      </TableHead>
                      <TableHead>Payload</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {logs && logs.length == 0 ? (
                      <TableRow key={0}>
                        <TableCell
                          colSpan={3}
                          className="font-mono text-center"
                        >
                          No logs found
                        </TableCell>
                      </TableRow>
                    ) : (
                      ''
                    )}
                    {sortedLogs.map((log, index) => (
                      <TableRow key={index}>
                        <TableCell className="font-mono">
                          {new Date(log.timestamp)
                            .toLocaleString('en-US', {
                              month: 'short',
                              day: '2-digit',
                              hour: '2-digit',
                              minute: '2-digit',
                              second: '2-digit',
                              fractionalSecondDigits: 2,
                              hour12: false,
                            })
                            .toUpperCase()
                            .replace(',', '')}
                        </TableCell>
                        <TableCell>
                          <Highlight
                            color={setColor(log.severity)}
                            textColor={setTextColor(log.severity)}
                          >
                            {log.severity}
                          </Highlight>
                        </TableCell>
                        <TableCell>
                          {typeof log.payload === 'object'
                            ? JSON.stringify(log.payload)
                            : String(log.payload)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </>
            )}
          </div>
        </main>
        <Pagination
          totalItems={logs?.length}
          itemsPerPage={itemsPerPage}
          currentPage={currentPage}
          onPageChange={paginate}
          className="mb-4"
        />
      </div>
    </div>
  );
};

export default LogTable;
