import type { AppProps } from 'next/app';
import { useTheme } from 'next-themes';
import { useEffect } from 'react';

import { ThemeProvider } from '@/components/ThemeProvider';

import '../styles/globals.css';

function MyApp({ Component, pageProps }: AppProps) {
  const { setTheme } = useTheme();

  useEffect(() => {
    setTheme('dark');
  });

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <Component {...pageProps} />
    </ThemeProvider>
  );
}

export default MyApp;
