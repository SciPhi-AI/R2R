import React from 'react';

interface SeparatorProps {
  className?: string;
  orientation?: 'horizontal' | 'vertical';
  decorative?: boolean;
}

const Separator = React.forwardRef<HTMLDivElement, SeparatorProps>(
  (
    { className, orientation = 'horizontal', decorative = false, ...props },
    ref
  ) => (
    <div
      ref={ref}
      role={decorative ? 'presentation' : 'separator'}
      aria-orientation={orientation}
      className={`border-t border-gray-200 ${className}`}
      {...props}
    />
  )
);

Separator.displayName = 'Separator';

export { Separator };
