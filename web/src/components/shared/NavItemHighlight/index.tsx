import React from 'react'; // Ensure React is imported if using JSX

interface NavItemHighlightProps {
  width: number;
  translateX: number;
  translateY: number;
}

export function NavItemHighlight({
  width,
  translateX,
  translateY,
}: NavItemHighlightProps) {
  return (
    <div
      className="absolute h-8 bg-[var(--color-3)] z-[-1] rounded-md transition ease-out duration-150"
      style={{
        width: `${width}px`,
        transform: `translate(${translateX}px, ${translateY}px)`,
        transitionProperty: 'width, transform, opacity',
      }}
    />
  );
}
