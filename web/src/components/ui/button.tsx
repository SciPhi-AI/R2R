import React from 'react';

interface ButtonProps {
  size?: 'sm' | 'md' | 'lg';
}

const renderInspectIcon = () => (
  <svg
    xmlns="http://www.w3.org/2000/svg"
    width="24"
    height="24"
    fill="currentColor"
    viewBox="0 0 24 24"
  >
    <path d="M9.5 3C4.81 3 1 6.81 1 11.5S4.81 20 9.5 20c1.64 0 3.16-.53 4.4-1.42l6.9 6.9 1.4-1.4-6.9-6.9C15.47 14.66 16 13.14 16 11.5 16 6.81 12.19 3 9.5 3zm0 2C12.54 5 15 7.46 15 10.5s-2.46 5.5-5.5 5.5S4 13.54 4 10.5 6.46 5 9.5 5zm0 2a3.5 3.5 0 100 7 3.5 3.5 0 000-7z" />
  </svg>
);

const Button: React.FC<ButtonProps> = ({ size }) => {
  return (
    <button
      className={`bg-black text-white px-4 py-2 rounded hover:bg-gray-700 transition-colors ${size === 'sm' ? 'text-xs' : size === 'md' ? 'text-sm' : 'text-lg'}`}
    >
      {renderInspectIcon()}
    </button>
  );
};

export default Button;
