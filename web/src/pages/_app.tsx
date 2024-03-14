import type { AppProps } from 'next/app';
import Head from 'next/head';
import { useRouter } from 'next/router';
import { useTheme } from 'next-themes';
import posthog from 'posthog-js';
import { PostHogProvider } from 'posthog-js/react';
import { useEffect } from 'react';

import { ThemeProvider } from '@/components/ThemeProvider';
import { AuthProvider } from '@/context/authProvider';
import { PipelineProvider } from '@/context/PipelineContext';

import '../styles/globals.css';

// Check that PostHog is client-side (used to handle Next.js SSR)
if (typeof window !== 'undefined') {
  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://app.posthog.com',
    // Enable debug mode in development
    loaded: (posthog) => {
      if (process.env.NODE_ENV === 'development') posthog.debug();
    },
  });
}

function MyApp({ Component, pageProps }: AppProps) {
  const { setTheme } = useTheme();
  const router = useRouter();

  useEffect(() => {
    setTheme('dark');
  });

  const options = {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST,
  };

  useEffect(() => {
    // Track page views
    const handleRouteChange = () => posthog?.capture('$pageview');
    router.events.on('routeChangeComplete', handleRouteChange);

    return () => {
      router.events.off('routeChangeComplete', handleRouteChange);
    };
  }, []);

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
        defaultTheme="dark"
        enableSystem={false}
        disableTransitionOnChange
      >
        <PostHogProvider client={posthog}>
          <PipelineProvider>
            <AuthProvider>
              <Component {...pageProps} />
            </AuthProvider>
          </PipelineProvider>
        </PostHogProvider>
      </ThemeProvider>
    </>
  );
}

export default MyApp;
