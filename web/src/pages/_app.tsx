import { useEffect, useState } from 'react';
import type { AppProps } from 'next/app';
import { AuthProvider } from '@/context/authProvider';
import { useTheme } from 'next-themes';

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
      <AuthProvider>
        <Component {...pageProps} />
      </AuthProvider>
    </ThemeProvider>
  );
}

export default MyApp;
