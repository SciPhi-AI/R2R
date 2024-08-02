import { ArrowRight } from 'lucide-react';
import { useRouter } from 'next/navigation';
import React, { FC, useState, useCallback } from 'react';

import { SearchProps } from '@/types';

function debounce<T extends (...args: any[]) => void>(
  func: T,
  wait: number
): (...args: Parameters<T>) => void {
  let timeout: NodeJS.Timeout | null = null;
  return function (this: ThisParameterType<T>, ...args: Parameters<T>) {
    if (timeout) {
      clearTimeout(timeout);
    }
    timeout = setTimeout(() => func.apply(this, args), wait);
  };
}

export const Search: FC<SearchProps> = ({
  pipeline,
  setQuery,
  placeholder,
  disabled = false,
}) => {
  const [value, setValue] = useState('');
  const router = useRouter();

  if (!placeholder) {
    placeholder = 'Search over your documents…';
  }

  const navigateToSearch = useCallback(
    debounce((searchValue: string) => {
      if (pipeline) {
        router.push(`/chat/?q=${encodeURIComponent(searchValue)}`);
      }
    }, 50),
    [router, pipeline]
  );

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (value.trim()) {
      navigateToSearch(value.trim());
      setQuery(value.trim());
      setValue('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="relative flex items-center focus-within:ring-2 focus-within:ring-blue-500 focus-within:ring-offset-2 focus-within:ring-offset-zinc-800 rounded-full">
        <input
          id="search-bar"
          value={value}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setValue(e.target.value)
          }
          autoFocus
          placeholder={placeholder}
          className="w-full px-4 py-2 h-10 bg-zinc-700 text-zinc-200 rounded-l-full focus:outline-none"
          disabled={disabled}
        />
        <button
          type="submit"
          className="px-4 py-2 h-10 bg-blue-500 text-white rounded-r-full hover:bg-blue-600 focus:outline-none transition-colors duration-200"
          disabled={disabled}
        >
          <ArrowRight size={20} />
        </button>
      </div>
    </form>
  );
};
