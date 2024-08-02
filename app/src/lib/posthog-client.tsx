// Anonymized telemetry data is sent to PostHog to help us improve the product. You can disable this by setting the R2R_DASHBOARD_DISABLE_TELEMETRY environment variable to 'true'.

import posthog from 'posthog-js';

const posthogApiKey = 'phc_OPBbibOIErCGc4NDLQsOrMuYFTKDmRwXX6qxnTr6zpU';
const posthogHost = 'https://us.i.posthog.com';

function initializePostHog() {
  if (typeof window === 'undefined') {
    return;
  }

  posthog.init(posthogApiKey, {
    api_host: posthogHost,
    autocapture: true,
  });

  if (process.env.R2R_DASHBOARD_DISABLE_TELEMETRY === 'true') {
    posthog.opt_out_capturing();
  }
}

export default posthog;
export { initializePostHog };
