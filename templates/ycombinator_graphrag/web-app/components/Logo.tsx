import Image from 'next/image';
import Link from 'next/link';
import React from 'react';

interface LogoProps {
  width?: number;
  height?: number;
  className?: string;
  onClick?: () => void;
  disableLink?: boolean;
  priority?: boolean;
}

export function Logo({
  width = 50,
  height = 50,
  className = '',
  onClick,
  disableLink = false,
  priority = true,
  ...rest
}: LogoProps) {
  const handleClick = (e: React.MouseEvent<HTMLElement, MouseEvent>) => {
    if (onClick) {
      e.preventDefault();
      onClick();
    }
  };

  const imageElement = (
    <Image
      alt="SciPhi Logo"
      src="/sciphi.svg"
      width={width}
      height={height}
      {...rest}
    />
  );

  const combinedClassName =
    `${className} ${disableLink ? 'cursor-default' : 'cursor-pointer'}`.trim();

  if (disableLink) {
    return (
      <div className={combinedClassName} onClick={handleClick}>
        {imageElement}
      </div>
    );
  }

  return (
    <Link
      href="/"
      passHref
      onClick={(e) => {
        e.preventDefault();
        window.location.reload();
      }}
      className={combinedClassName}
    >
      {imageElement}
    </Link>
  );
}
