import '@/styles/globals.css';
import type { AppProps } from 'next/app';
import { useEffect } from 'react';
import { useRouter } from 'next/router';
import posthog from 'posthog-js';

export default function App({ Component, pageProps }: AppProps) {
  const router = useRouter();

  useEffect(() => {
    // Initialize PostHog
    posthog.init(
      process.env.NEXT_PUBLIC_POSTHOG_KEY ||
        'phc_bcK7yMQ41RnFN2cuUjC99XuJpI50mNvI3DdqkEE0uI1',
      {
        api_host: 'https://us.i.posthog.com',
        person_profiles: 'identified_only',
      }
    );

    // Track page views
    const handleRouteChange = () => posthog.capture('$pageview');
    router.events.on('routeChangeComplete', handleRouteChange);

    return () => {
      router.events.off('routeChangeComplete', handleRouteChange);
    };
  }, [router.events]);

  return <Component {...pageProps} />;
}
