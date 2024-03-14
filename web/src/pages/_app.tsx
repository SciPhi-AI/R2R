import type { AppProps } from 'next/app';
import Head from 'next/head';
import { useTheme } from 'next-themes';
import { useEffect } from 'react';

import { ThemeProvider } from '@/components/ThemeProvider';
import { AuthProvider } from '@/context/authProvider';
import { PipelineProvider } from '@/context/PipelineContext';

import '../styles/globals.css';

function MyApp({ Component, pageProps }: AppProps) {
  const { setTheme } = useTheme();

  useEffect(() => {
    setTheme('dark');
  });

  const options = {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
  };

  return (
    <>
      <Head>
        <title>SciPhi Cloud</title>

        <link rel="icon" href="public/favicon.ico" />
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin=""
        />
        <link
          href="https://fonts.googleapis.com/css2?family=Ubuntu:wght@400;500;600;700&display=swap"
          rel="stylesheet"
        />
        {/* Add other global stylesheets or links here */}
      </Head>

      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        <PipelineProvider>
          <AuthProvider>
            <Component {...pageProps} />
          </AuthProvider>
        </PipelineProvider>
      </ThemeProvider>
    </>
  );
}

export default MyApp;
