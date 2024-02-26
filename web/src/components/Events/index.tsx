import { useRouter } from 'next/router';
import React, { useState, useMemo, useEffect } from 'react';

// Internal imports from the project
import Highlight from '@/components/ui/highlight';
import { Input } from '@/components/ui/input';
import Pagination from '@/components/ui/pagination';
import useLogs from '@/hooks/useLogs';
import { setColor } from '@/lib/utils';

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';

// Define your dictionary
const methodDictionary: { [key: string]: string } = {
  'Generate Completion': 'RAG',
  Search: 'Search',
};

const changeMethod = (method: string) => {
  return methodDictionary[method] || method;
};

export function Event() {
  const router = useRouter();

  const handleRowClick = (runId: string) => {
    router.push(`/event/${runId}`);
  };

  const { logs, loading, error } = useLogs();

  console.log('logs = ', logs);

  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  const indexOfLastItem = currentPage * itemsPerPage;
  const indexOfFirstItem = indexOfLastItem - itemsPerPage;
  const currentItems = logs.slice(indexOfFirstItem, indexOfLastItem);

  const paginate = (pageNumber: number) => setCurrentPage(pageNumber);

  const truncateText = (text: string, limit: number) => {
    return text.length > limit ? text.substring(0, limit) + '...' : text;
  };

  const [sortField, setSortField] = useState<string | null>('timestamp');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');
  const [filterQuery, setFilterQuery] = useState('');
  console.log('log.searchResults=', logs[0]?.searchResults);

  // Sorting function
  const sortedItems = useMemo(() => {
    if (!sortField) return currentItems;

    return [...currentItems].sort((a, b) => {
      let valueA = a[sortField];
      let valueB = b[sortField];
      if (sortField === 'score') {
        valueA = parseFloat(a.score);
        valueB = parseFloat(b.score);
      }

      if (valueA < valueB) return sortDirection === 'asc' ? -1 : 1;
      if (valueA > valueB) return sortDirection === 'asc' ? 1 : -1;
      return 0;
    });
  }, [currentItems, sortField, sortDirection]);

  // Filtering function
  const filteredAndSortedItems = useMemo(() => {
    return sortedItems.filter((item) => {
      const itemValuesIncludeQuery = Object.values(item).some((value) =>
        value.toString().toLowerCase().includes(filterQuery.toLowerCase())
      );
      return itemValuesIncludeQuery;
    });
  }, [sortedItems, filterQuery]);

  return (
    <div className="min-h-screen w-full p-2">
      <div className="flex flex-col">
        <header className="flex h-14 lg:h-[60px] items-center gap-4 border-b bg-gray-100/40 px-2 dark:bg-gray-800/40 mb-4">
          <div className="w-full flex-1">
            <form>
              <div className="relative">
                <SearchIcon className="absolute left-2.5 top-2.5 h-4 w-4 text-gray-500 dark:text-gray-400" />
                <Input
                  className="w-full bg-white shadow-none appearance-none pl-8 dark:bg-gray-950"
                  placeholder="Search runs..."
                  type="search"
                  value={filterQuery}
                  onChange={(e) => setFilterQuery(e.target.value)}
                />
              </div>
            </form>
          </div>
        </header>
        <main className="flex flex-1 flex-col gap-4 md:gap-8 mx-2 mb-4">
          <div className="border shadow-sm rounded-lg w-full">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead
                    className="flex-none w-0"
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
                    className="flex-2 w-0"
                    onClick={() => {
                      setSortField('event');
                      setSortDirection(
                        sortDirection === 'asc' ? 'desc' : 'asc'
                      );
                    }}
                  >
                    Event
                  </TableHead>
                  <TableHead
                    className="flex-3"
                    onClick={() => {
                      setSortField('searchQuery');
                      setSortDirection(
                        sortDirection === 'asc' ? 'desc' : 'asc'
                      );
                    }}
                  >
                    Search Query
                  </TableHead>
                  <TableHead
                    className="flex-3"
                    onClick={() => {
                      setSortField('searchResults');
                      setSortDirection(
                        sortDirection === 'asc' ? 'desc' : 'asc'
                      );
                    }}
                  >
                    Search Results
                  </TableHead>
                  <TableHead
                    className="flex-4"
                    onClick={() => {
                      setSortField('completionResult');
                      setSortDirection(
                        sortDirection === 'asc' ? 'desc' : 'asc'
                      );
                    }}
                  >
                    Completion Result
                  </TableHead>
                  <TableHead
                    className="flex-2 w-0"
                    onClick={() => {
                      setSortField('outcome');
                      setSortDirection(
                        sortDirection === 'asc' ? 'desc' : 'asc'
                      );
                    }}
                  >
                    Outcome
                  </TableHead>
                  <TableHead
                    className="flex-2"
                    onClick={() => {
                      setSortField('score');
                      setSortDirection(
                        sortDirection === 'asc' ? 'desc' : 'asc'
                      );
                    }}
                  >
                    Score
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredAndSortedItems.map((log, index) => (
                  <TableRow
                    key={index}
                    onClick={() => handleRowClick(log.pipelineRunId)}
                    style={{ cursor: 'pointer' }}
                  >
                    <TableCell className="p-4 align-middle">
                      {log.timestamp}
                    </TableCell>
                    <TableCell>
                      <Highlight color={setColor(changeMethod(log.method))}>
                        {changeMethod(log.method)}
                      </Highlight>
                    </TableCell>
                    <TableCell>
                      {log.searchQuery ? truncateText(log.searchQuery, 30) : ''}
                    </TableCell>
                    <TableCell>
                      {log.searchResults && log.searchResults.length > 0
                        ? truncateText(log.searchResults[0]?.text, 30)
                        : ''}
                    </TableCell>
                    <TableCell>
                      {log.completionResult
                        ? truncateText(log.completionResult, 50)
                        : ''}
                    </TableCell>
                    <TableCell>
                      <Highlight color={setColor(log.outcome)}>
                        {log.outcome === 'success' ? '✓' : '✗'}
                      </Highlight>
                    </TableCell>
                    <TableCell>
                      {log.outcome === 'success' ? log.score : ''}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        </main>
        <Pagination
          totalItems={logs.length}
          itemsPerPage={itemsPerPage}
          currentPage={currentPage}
          onPageChange={paginate}
          className="mb-4"
        />
      </div>
    </div>
  );
}

function SearchIcon(props: React.SVGProps<SVGSVGElement>) {
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
      <circle cx="11" cy="11" r="8" />
      <path d="m21 21-4.3-4.3" />
    </svg>
  );
}
