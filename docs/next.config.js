const withNextra = require('nextra')({
  theme: 'nextra-theme-docs',
  themeConfig: './theme.config.tsx',
});

require('dotenv').config({ path: './.env.local' });

module.exports = withNextra({
  // Add the environment variables to the Next.js configuration
  env: {
    INKEEP_API_KEY: process.env.INKEEP_API_KEY,
    INKEEP_INT_ID: process.env.INKEEP_INT_ID,
    INKEEP_ORG_ID: process.env.INKEEP_ORG_ID,
    NEXT_PUBLIC_POSTHOG_KEY: 'phc_OPBbibOIErCGc4NDLQsOrMuYFTKDmRwXX6qxnTr6zpU',
    NEXT_PUBLIC_POSTHOG_HOST: 'https://us.i.posthog.com'
  },
});
