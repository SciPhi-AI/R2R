import Image from 'next/image';
import Link from 'next/link';
import React from 'react';

import { LogoProps } from '@/types';

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
      src="/images/sciphi.svg"
      width={width}
      height={height}
      priority={priority}
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
    <Link href="/" passHref onClick={handleClick} className={combinedClassName}>
      {imageElement}
    </Link>
  );
}
