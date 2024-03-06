import Link from 'next/link';

import {
  FileTextIcon,
  ServerIcon,
  DatabaseIcon,
  UserIcon,
  AlertTriangleIcon,
} from '@/components/icons';

const Sidebar = () => {
  return (
    <div className="flex h-full max-h-screen flex-col gap-2">
      <div className="flex h-[60px] items-center border-b px-6">
        <Link className="flex items-center gap-2 font-semibold" href="#">
          <FileTextIcon className="h-6 w-6" />
          <span>Log Dashboard</span>
        </Link>
      </div>
      <div className="flex-1 overflow-auto py-2">
        <nav className="grid items-start px-4 text-sm font-medium">
          <Link
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-gray-500 transition-all hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-50"
            href="#"
          >
            <ServerIcon className="h-4 w-4" />
            Server Logs
          </Link>
          <Link
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-gray-500 transition-all hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-50"
            href="#"
          >
            <DatabaseIcon className="h-4 w-4" />
            Database Logs
          </Link>
          <Link
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-gray-500 transition-all hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-50"
            href="#"
          >
            <UserIcon className="h-4 w-4" />
            User Activity Logs
          </Link>
          <Link
            className="flex items-center gap-3 rounded-lg px-3 py-2 text-gray-500 transition-all hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-50"
            href="#"
          >
            <AlertTriangleIcon className="h-4 w-4" />
            Error Logs
          </Link>
        </nav>
      </div>
    </div>
  );
};

export default Sidebar;
