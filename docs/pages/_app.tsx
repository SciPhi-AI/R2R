// pages/_app.tsx

import type { AppProps } from 'next/app';
import { useEffect } from 'react';
import { useRouter } from 'next/router';
import posthog from 'posthog-js';
import { PostHogProvider } from 'posthog-js/react';
import 'swagger-ui-react/swagger-ui.css';
import '../public/redoc.css';

if (typeof window !== 'undefined') {
  posthog.init(process.env.NEXT_PUBLIC_POSTHOG_KEY, {
    api_host: process.env.NEXT_PUBLIC_POSTHOG_HOST || 'https://us.i.posthog.com',
    person_profiles: 'identified_only',
    loaded: (posthog) => {
      if (process.env.NODE_ENV === 'development') {
        posthog.debug();
      }
    },
    capture_pageview: false, // Disable automatic pageview capture, as we capture manually
    capture_pageleave: true // Enable automatic pageleave capture
  });
}

function MyApp({ Component, pageProps }: AppProps) {
  const router = useRouter();

  useEffect(() => {
    // Track page views
    const handleRouteChange = () => posthog.capture('$pageview');
    router.events.on('routeChangeComplete', handleRouteChange);

    return () => {
      router.events.off('routeChangeComplete', handleRouteChange);
    };
  }, [router.events]);

  return (
    <PostHogProvider client={posthog}>
      <Component {...pageProps} />
    </PostHogProvider>
  );
}

export default MyApp;