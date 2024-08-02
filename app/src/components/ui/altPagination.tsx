import React from 'react';

const Pagination: React.FC<{
  currentPage: number;
  totalPages: number;
  onPageChange: (pageNumber: number) => void;
}> = ({ currentPage, totalPages, onPageChange }) => {
  if (totalPages <= 1) {
    return (
      <div className="flex justify-center items-center mt-4">
        <span className="text-gray-500">Page 1 of 1</span>
      </div>
    );
  }
  const isPreviousDisabled = currentPage === 1;
  const isNextDisabled = currentPage === totalPages || totalPages === 1;

  const getPageNumbers = () => {
    const pageNumbers = [];
    const maxPages = 5; // Reduced to accommodate new buttons
    const halfMaxPages = Math.floor(maxPages / 2);

    let startPage = Math.max(currentPage - halfMaxPages, 2);
    const endPage = Math.min(startPage + maxPages - 1, totalPages - 1);

    if (endPage - startPage + 1 < maxPages) {
      startPage = Math.max(endPage - maxPages + 1, 2);
    }

    for (let i = startPage; i <= endPage; i++) {
      pageNumbers.push(i);
    }

    return pageNumbers;
  };

  const handleJump = (direction: 'backward' | 'forward') => {
    const jump = direction === 'backward' ? -10 : 10;
    const newPage = Math.max(1, Math.min(currentPage + jump, totalPages));
    onPageChange(newPage);
  };

  return (
    <div className="flex justify-center items-center mt-4">
      <button
        onClick={() => handleJump('backward')}
        disabled={currentPage <= 10}
        className={`px-2 py-1 mx-1 rounded ${
          currentPage <= 10
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-blue-500 text-white'
        }`}
      >
        &#8810; {/* <<< */}
      </button>
      <button
        onClick={() => onPageChange(currentPage - 1)}
        disabled={isPreviousDisabled}
        className={`px-4 py-2 mx-1 rounded ${
          isPreviousDisabled
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-blue-500 text-white'
        }`}
      >
        &lt; Previous
      </button>
      <button
        onClick={() => onPageChange(1)}
        className={`px-4 py-2 mx-1 rounded ${
          currentPage === 1
            ? 'bg-blue-500 text-white'
            : 'bg-zinc-800 text-zinc-400'
        }`}
      >
        1
      </button>
      {currentPage > 3 && <span className="mx-1">...</span>}
      {getPageNumbers().map((pageNumber) => (
        <button
          key={pageNumber}
          onClick={() => onPageChange(pageNumber)}
          className={`px-4 py-2 mx-1 rounded ${
            currentPage === pageNumber
              ? 'bg-blue-500 text-white'
              : 'bg-zinc-800 text-zinc-400'
          }`}
        >
          {pageNumber}
        </button>
      ))}
      {currentPage < totalPages - 2 && <span className="mx-1">...</span>}
      {totalPages > 1 && (
        <button
          onClick={() => onPageChange(totalPages)}
          className={`px-4 py-2 mx-1 rounded ${
            currentPage === totalPages
              ? 'bg-blue-500 text-white'
              : 'bg-zinc-800 text-zinc-400'
          }`}
        >
          {totalPages}
        </button>
      )}
      <button
        onClick={() => onPageChange(currentPage + 1)}
        disabled={isNextDisabled}
        className={`px-4 py-2 mx-1 rounded ${
          isNextDisabled
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-blue-500 text-white'
        }`}
      >
        Next &gt;
      </button>
      <button
        onClick={() => handleJump('forward')}
        disabled={currentPage > totalPages - 10}
        className={`px-2 py-1 mx-1 rounded ${
          currentPage > totalPages - 10
            ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
            : 'bg-blue-500 text-white'
        }`}
      >
        &#8811; {/* >>> */}
      </button>
    </div>
  );
};

export default Pagination;
