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

  const isCloudMode = process.env.NEXT_PUBLIC_CLOUD_MODE === 'true';

  const renderContent = () => {
    // If in cloud mode, wrap Component with AuthProvider
    if (isCloudMode) {
      return (
        <AuthProvider>
          <Component {...pageProps} />
        </AuthProvider>
      );
    }
    // If not in cloud mode, render Component without AuthProvider
    return <Component {...pageProps} />;
  };

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      {renderContent()}
    </ThemeProvider>
  );
}

export default MyApp;
