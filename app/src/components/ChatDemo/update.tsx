'use client';
import React, { useState, useRef, FormEvent, ChangeEvent } from 'react';

import { useUserContext } from '@/context/UserContext';
import { UpdateButtonProps } from '@/types';

export const UpdateButton: React.FC<UpdateButtonProps> = ({
  documentId,
  onUpdateSuccess,
  showToast = () => {},
}) => {
  const [isUpdating, setIsUpdating] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { getClient } = useUserContext();

  const handleDocumentUpdate = async (
    event: FormEvent<HTMLFormElement> | ChangeEvent<HTMLInputElement>
  ) => {
    event.preventDefault();
    if (
      fileInputRef.current &&
      fileInputRef.current.files &&
      fileInputRef.current.files.length
    ) {
      setIsUpdating(true);
      const file = fileInputRef.current.files[0];

      try {
        const client = await getClient();
        if (!client) {
          throw new Error('Failed to get authenticated client');
        }

        const metadata = { title: file.name };

        await client.updateFiles([file], {
          document_ids: [documentId],
          metadatas: [metadata],
        });
        showToast({
          variant: 'success',
          title: 'Update Successful',
          description: 'The document has been updated',
        });
        onUpdateSuccess();
      } catch (error: unknown) {
        console.error('Error updating file:', error);
        let errorMessage = 'An unknown error occurred';
        if (error instanceof Error) {
          errorMessage = error.message;
        }
        showToast({
          variant: 'destructive',
          title: 'Update Failed',
          description: errorMessage,
        });
      } finally {
        setIsUpdating(false);
        if (fileInputRef.current) {
          fileInputRef.current.value = '';
        }
      }
    }
  };

  const handleUpdateButtonClick = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div style={{ zIndex: 1000 }}>
      <form onSubmit={handleDocumentUpdate}>
        <input
          type="file"
          ref={fileInputRef}
          style={{ display: 'none' }}
          onChange={handleDocumentUpdate}
        />
        <button
          type="button"
          onClick={handleUpdateButtonClick}
          disabled={isUpdating}
          className={`${
            isUpdating
              ? 'bg-gray-400 cursor-not-allowed'
              : 'hover:bg-blue-700 bg-blue-500'
          } text-white font-bold py-1 px-2 rounded`}
        >
          {isUpdating ? <span className="animate-spin">↻</span> : '↺'}
        </button>
      </form>
    </div>
  );
};
