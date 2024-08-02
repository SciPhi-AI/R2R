import React from 'react';

import { HighlightProps } from '@/types';

const Highlight: React.FC<HighlightProps> = ({
  color,
  textColor,
  children,
}) => {
  return (
    <span className={`px-2 py-1 ${color} rounded ${textColor}`}>
      {children}
    </span>
  );
};

export default Highlight;
