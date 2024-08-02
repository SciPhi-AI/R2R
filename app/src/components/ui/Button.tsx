import clsx from 'clsx';
import Link from 'next/link';
import React from 'react';

const variantStyles = {
  primary:
    'bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-blue-600/10 dark:text-blue-600 dark:ring-1 dark:ring-inset dark:ring-blue-600/20 dark:hover:bg-blue-600/10 dark:hover:text-blue-300 dark:hover:ring-blue-300',
  secondary:
    'text-zinc-900 hover:bg-zinc-200 dark:bg-zinc-800/40 dark:text-zinc-400 dark:ring-1 dark:ring-inset dark:ring-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-300',
  filled:
    'bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-blue-600 dark:text-white dark:hover:bg-opacity-90',
  outline:
    'px-3 text-zinc-700 ring-1 ring-inset ring-zinc-900/10 hover:bg-zinc-900/2.5 hover:text-zinc-900 dark:text-zinc-400 dark:ring-white/10 dark:hover:bg-white/5 dark:hover:text-white',
  danger:
    'bg-red-600 text-white hover:bg-red-500 dark:bg-red-600 dark:text-white dark:hover:bg-red-500',
  amber:
    'bg-amber-500 text-white hover:bg-amber-600 dark:bg-amber-500 dark:text-white dark:hover:bg-amber-600',
  text: 'text-blue-600 hover:text-blue-600 dark:text-blue-600 dark:hover:text-blue-600',
  disabled: 'bg-zinc-600 text-white cursor-not-allowed hover:bg-zinc-500',
  light: 'bg-zinc-700 text-white hover:bg-zinc-600',
};

type ButtonProps = {
  variant?: keyof typeof variantStyles;
  className?: string;
  href?: string;
  disabled?: boolean;
} & React.ButtonHTMLAttributes<HTMLButtonElement>;

export function Button({
  variant = 'primary',
  className,
  children,
  href,
  disabled = false,
  ...props
}: ButtonProps) {
  const buttonClassName = clsx(
    'rounded-md inline-flex gap-0.5 justify-center overflow-hidden font-medium transition',
    variantStyles[variant],
    className
  );

  const commonProps = {
    className: buttonClassName,
    disabled: disabled,
  };

  if (href && !disabled) {
    return (
      <Link
        href={href}
        {...commonProps}
        {...(props as React.AnchorHTMLAttributes<HTMLAnchorElement>)}
      >
        {children}
      </Link>
    );
  }

  return (
    <button {...commonProps} {...props}>
      {children}
    </button>
  );
}
