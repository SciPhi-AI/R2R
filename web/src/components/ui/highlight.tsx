import React from 'react';

interface HighlightProps {
  color: string; // Accept any string
  children: React.ReactNode;
}

const Highlight: React.FC<HighlightProps> = ({ color, children }) => {
  return <span className={`px-2 py-1 ${color} rounded`}>{children}</span>;
};

export default Highlight;
