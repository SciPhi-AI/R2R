import clsx from 'clsx';
import Link from 'next/link';

const variantStyles = {
  primary:
    'bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-indigo-400/10 dark:text-indigo-400 dark:ring-1 dark:ring-inset dark:ring-indigo-400/20 dark:hover:bg-indigo-400/10 dark:hover:text-indigo-300 dark:hover:ring-indigo-300',
  secondary:
    'text-zinc-900 hover:bg-zinc-200 dark:bg-zinc-800/40 dark:text-zinc-400 dark:ring-1 dark:ring-inset dark:ring-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-300',
  filled:
    'bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-indigo-600 dark:text-white dark:hover:bg-opacity-90',
  outline:
    'px-3 text-zinc-700 ring-1 ring-inset ring-zinc-900/10 hover:bg-zinc-900/2.5 hover:text-zinc-900 dark:text-zinc-400 dark:ring-white/10 dark:hover:bg-white/5 dark:hover:text-white',
  danger:
    'bg-red-600 text-white hover:bg-red-500 dark:bg-red-600 dark:text-white dark:hover:bg-red-500',
  text: 'text-indigo-500 hover:text-indigo-600 dark:text-indigo-400 dark:hover:text-indigo-500',
  disabled: 'bg-zinc-500 text-white cursor-not-allowed hover:bg-zinc-300',
};

type ButtonProps = {
  variant?: keyof typeof variantStyles;
  className?: string;
  href?: string;
  disabled?: boolean;
} & React.ComponentPropsWithoutRef<'button'>;

export function Button({
  variant = 'primary',
  className,
  children,
  href,
  disabled = false,
  ...props
}: ButtonProps) {
  className = clsx(
    'rounded-md inline-flex gap-0.5 justify-center overflow-hidden font-medium transition',
    variantStyles[variant],
    className
  );

  // Render a link with a button inside if href is provided
  if (href && !disabled) {
    // Check disabled state
    return (
      <Link href={href}>
        <button className={className} {...props}>
          {children}
        </button>
      </Link>
    );
  }

  // Render a button if no href is provided
  return (
    <button className={className} disabled={disabled} {...props}>
      {children}
    </button>
  );
}
