import type { AppProps } from 'next/app';
import { useTheme } from 'next-themes';
import { useEffect } from 'react';
import { ProviderContextProvider } from '@/context/providerContext';

import { ThemeProvider } from '@/components/ThemeProvider';

import '../styles/globals.css';

function MyApp({ Component, pageProps }: AppProps) {
  const { setTheme } = useTheme();

  useEffect(() => {
    setTheme('dark');
  });

  return (
    <ProviderContextProvider>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        <Component {...pageProps} />
      </ThemeProvider>
    </ProviderContextProvider>
  );
}

export default MyApp;
