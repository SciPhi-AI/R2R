'use client';
import { Loader, ChevronLeft, ChevronRight } from 'lucide-react';
import React, { useState, useEffect, useCallback } from 'react';

import Layout from '@/components/Layout';
import { Button } from '@/components/ui/Button';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useUserContext } from '@/context/UserContext';
import { formatFileSize } from '@/lib/utils';

const USERS_PER_PAGE = 10;

const UserTable = ({ users }: { users: any[] }) => {
  const [currentPage, setCurrentPage] = useState(1);
  const totalPages = Math.ceil(users.length / USERS_PER_PAGE);

  const paginatedUsers = users.slice(
    (currentPage - 1) * USERS_PER_PAGE,
    currentPage * USERS_PER_PAGE
  );

  const filledUsers = [
    ...paginatedUsers,
    ...Array(USERS_PER_PAGE - paginatedUsers.length).fill(null),
  ];

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-1/3">User ID</TableHead>
            <TableHead className="w-1/3">Number of Files</TableHead>
            <TableHead className="w-1/3">Total Size</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {filledUsers.map((user, index) => (
            <TableRow key={user ? user.user_id : `empty-${index}`}>
              {user ? (
                <>
                  <TableCell className="font-medium">{user.user_id}</TableCell>
                  <TableCell>{user.num_files}</TableCell>
                  <TableCell>
                    {formatFileSize(user.total_size_in_bytes)}
                  </TableCell>
                </>
              ) : (
                <>
                  <TableCell className="font-medium">&nbsp;</TableCell>
                  <TableCell>&nbsp;</TableCell>
                  <TableCell>&nbsp;</TableCell>
                </>
              )}
            </TableRow>
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
          disabled={currentPage === totalPages || users.length === 0}
        >
          Next
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
};

const Index: React.FC = () => {
  const [isLoading, setIsLoading] = useState(true);
  const [users, setUsers] = useState<any[]>([]);
  const { getClient, pipeline } = useUserContext();

  const fetchUsers = useCallback(async () => {
    try {
      const client = await getClient();
      if (!client) {
        throw new Error('Failed to get authenticated client');
      }

      const data = await client.usersOverview();
      setUsers(data.results || []);
    } catch (error) {
      console.error('Error fetching users:', error);
    } finally {
      setIsLoading(false);
    }
  }, [getClient]);

  useEffect(() => {
    if (pipeline?.deploymentUrl) {
      fetchUsers();
    }
  }, [fetchUsers, pipeline?.deploymentUrl]);

  return (
    <Layout pageTitle="Users Overview" includeFooter={false}>
      <main className="w-full flex flex-col min-h-screen container">
        <div className="absolute inset-0 bg-zinc-900 mt-[5rem] sm:mt-[5rem] ">
          <div className="mx-auto max-w-6xl mb-12 mt-4 absolute inset-4 md:inset-1">
            {isLoading ? (
              <Loader className="mx-auto mt-20 animate-spin" size={64} />
            ) : (
              <UserTable users={users} />
            )}
          </div>
        </div>
      </main>
    </Layout>
  );
};

export default Index;
