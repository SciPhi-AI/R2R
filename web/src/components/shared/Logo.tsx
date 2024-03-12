import Image from 'next/image';
import Link from 'next/link'; // Import Link from next/link
import React from 'react';

interface LogoProps {
  width?: number;
  height?: number;
  className?: string;
}
export function Logo({
  width = 25,
  height = 25,
  className = 'cursor-pointer',
  ...rest
}: LogoProps) {
  return (
    <Link href="/" passHref>
      <Image
        alt="sciphi.png"
        src="/images/sciphi.png"
        width={width}
        height={height}
        className={className}
        {...rest} // Now rest only contains props that are compatible with the Image component
      />
    </Link>
  );
}
