import React from 'react';

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog';
import { useUserContext } from '@/context/UserContext';
import { DeleteButtonProps } from '@/types';

export const DeleteButton: React.FC<DeleteButtonProps> = ({
  selectedDocumentIds,
  onDelete,
  onSuccess,
  showToast,
}) => {
  const { getClient } = useUserContext();

  const handleBatchDelete = async () => {
    if (selectedDocumentIds.length === 0) {
      return;
    }

    try {
      const client = await getClient();
      if (!client) {
        throw new Error('Failed to get authenticated client');
      }

      for (let i = 0; i < selectedDocumentIds.length; i++) {
        const key = 'document_id';
        const value = selectedDocumentIds[i];

        await client.delete([key], [value]);
      }
      showToast({
        variant: 'success',
        title: 'Documents deleted',
        description: 'The selected documents have been successfully deleted',
      });
      onSuccess();
      onDelete();
    } catch (error: unknown) {
      console.error('Error deleting documents:', error);
      if (error instanceof Error) {
        showToast({
          variant: 'destructive',
          title: 'Failed to delete documents',
          description: error.message,
        });
      } else {
        showToast({
          variant: 'destructive',
          title: 'Failed to delete documents',
          description: 'An unknown error occurred',
        });
      }
    }
  };

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <button
          className={`pl-2 pr-2 text-white py-2 px-4 rounded-full ${
            selectedDocumentIds.length === 0
              ? 'bg-red-400 cursor-not-allowed'
              : 'bg-red-500 hover:bg-red-600'
          }`}
          disabled={selectedDocumentIds.length === 0}
        >
          Delete File(s)
        </button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>
            Are you sure you want to delete the selected documents?
          </AlertDialogTitle>
          <AlertDialogDescription>
            This action cannot be undone. The selected documents will be
            permanently deleted.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction onClick={handleBatchDelete}>
            Delete
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};
