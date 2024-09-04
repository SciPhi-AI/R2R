import { ArrowRight, Trash2 } from 'lucide-react';
import React, { FC, useState } from 'react';

interface SearchProps {
  setQuery: (query: string) => void;
  placeholder?: string;
  onClear: () => void;
  isStreaming: boolean;
}

export const Search: FC<SearchProps> = ({
  setQuery,
  placeholder = 'Start a conversation...',
  onClear,
  isStreaming,
}) => {
  const [value, setValue] = useState('');

  const handleSubmit = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    if (value.trim() && !isStreaming) {
      setQuery(value.trim());
      setValue('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="w-full">
      <div className="relative flex items-center rounded-full overflow-hidden">
        <button
          type="button"
          onClick={onClear}
          className={`px-3 py-2 h-10 bg-input text-foreground rounded-l-full hover:bg-input/90 focus:outline-none focus:ring-2 focus:ring-primary transition-colors duration-200 outline-none ${
            isStreaming
              ? 'opacity-50 cursor-not-allowed'
              : 'hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary'
          }`}
          disabled={isStreaming}
        >
          <Trash2 size={20} />
        </button>
        <input
          id="search-bar"
          value={value}
          onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
            setValue(e.target.value)
          }
          autoFocus
          placeholder={placeholder}
          className="w-full px-4 py-2 h-10 bg-input text-foreground focus:outline-none focus:ring-2 focus:ring-primary outline-none"
        />
        <style jsx>{`
          input:-webkit-autofill,
          input:-webkit-autofill:hover,
          input:-webkit-autofill:focus,
          input:-webkit-autofill:active {
            -webkit-background-clip: text;
            -webkit-text-fill-color: var(--foreground) !important;
            transition: background-color 5000s ease-in-out 0s;
            box-shadow: inset 0 0 20px 20px var(--input-background-color);
          }
        `}</style>
        <button
          type="submit"
          className={`px-4 py-2 h-10 bg-primary text-primary-foreground rounded-r-full transition-colors duration-200 outline-none ${
            isStreaming
              ? 'opacity-50 cursor-not-allowed'
              : 'hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-primary'
          }`}
          disabled={isStreaming}
        >
          <ArrowRight size={20} />
        </button>
      </div>
    </form>
  );
};
