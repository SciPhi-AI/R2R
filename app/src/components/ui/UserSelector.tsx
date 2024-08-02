import React, { useState } from 'react';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface UserSelectorProps {
  id?: string;
  selectedUserId: string;
  setSelectedUserId: (userId: string) => void;
}

const UserSelector: React.FC<UserSelectorProps> = ({
  id,
  selectedUserId,
  setSelectedUserId,
}) => {
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const handleValueChange = (value: string) => {
    if (value === 'addUser') {
      setIsDialogOpen(true);
    } else {
      setSelectedUserId(value);
    }
  };

  const handleAddUser = () => {
    const newUserId = generatePlaceholderUserId();
    setSelectedUserId(newUserId);
    setIsDialogOpen(false);
  };

  const generatePlaceholderUserId = () => {
    return 'user-' + Math.random().toString(36).substr(2, 9);
  };

  return (
    <>
      <div id={id}>
        <Select value={selectedUserId} onValueChange={handleValueChange}>
          <SelectTrigger>
            <SelectValue
              className="w-full"
              style={{ textAlign: 'left', overflow: 'auto' }}
            >
              {selectedUserId || 'Select a user'}
            </SelectValue>
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="063edaf8-3e63-4cb9-a4d6-a855f36376c3">
              063edaf8-3e63-4cb9-a4d6-a855f36376c3
            </SelectItem>
            <SelectItem value="addUser">Add a User</SelectItem>
          </SelectContent>
        </Select>

        <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Add a new user</DialogTitle>
              <DialogDescription>
                Click the button below to generate a new user ID.
              </DialogDescription>
            </DialogHeader>
            <div>
              <button
                onClick={handleAddUser}
                className="mt-4 inline-flex justify-center py-2 px-4 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500"
              >
                Generate New User ID
              </button>
            </div>
          </DialogContent>
        </Dialog>
      </div>
    </>
  );
};

export default UserSelector;
