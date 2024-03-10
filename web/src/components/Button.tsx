import clsx from 'clsx';

const variantStyles = {
  primary:
    'bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-indigo-400/10 dark:text-indigo-400 dark:ring-1 dark:ring-inset dark:ring-indigo-400/20 dark:hover:bg-indigo-400/10 dark:hover:text-indigo-300 dark:hover:ring-indigo-300',
  secondary:
    'text-zinc-900 hover:bg-zinc-200 dark:bg-zinc-800/40 dark:text-zinc-400 dark:ring-1 dark:ring-inset dark:ring-zinc-800 dark:hover:bg-zinc-800 dark:hover:text-zinc-300',
  filled:
    'bg-zinc-900 text-white hover:bg-zinc-700 dark:bg-indigo-600 dark:text-white dark:hover:bg-opacity-90',
  outline:
    'px-3 text-zinc-700 ring-1 ring-inset ring-zinc-900/10 hover:bg-zinc-900/2.5 hover:text-zinc-900 dark:text-zinc-400 dark:ring-white/10 dark:hover:bg-white/5 dark:hover:text-white',
  text: 'text-indigo-500 hover:text-indigo-600 dark:text-indigo-400 dark:hover:text-indigo-500',
};

type ButtonProps = {
  variant?: keyof typeof variantStyles;
} & React.ComponentPropsWithoutRef<'button'>;

export function Button({
  variant = 'primary',
  className,
  children,
  ...props
}: ButtonProps) {
  className = clsx(
    'rounded-md inline-flex gap-0.5 px-3 justify-center overflow-hidden text-sm font-medium transition',
    variantStyles[variant],
    className
  );

  return (
    <button className={className} {...props}>
      {children}
    </button>
  );
}
