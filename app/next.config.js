module.exports = {
  reactStrictMode: false,
  output: 'standalone',
  webpack: (config, { isServer }) => {
    if (!isServer) {
      config.resolve.fallback = {
        ...config.resolve.fallback,
        fs: false,
      };
    }
    return config;
  },
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'github.com',
      },
      {
        protocol: 'https',
        hostname: 'lh3.googleusercontent.com',
      },
    ],
  },
  env: {
    CLOUD_INKEEP_API_KEY: process.env.CLOUD_INKEEP_API_KEY,
    CLOUD_INKEEP_INT_ID: process.env.CLOUD_INKEEP_INT_ID,
    CLOUD_INKEEP_ORG_ID: process.env.CLOUD_INKEEP_ORG_ID,
    CLOUD_DOCS_INKEEP_API_KEY: process.env.CLOUD_DOCS_INKEEP_API_KEY,
    CLOUD_DOCS_INKEEP_INT_ID: process.env.CLOUD_DOCS_INKEEP_INT_ID,
    CLOUD_DOCS_INKEEP_ORG_ID: process.env.CLOUD_DOCS_INKEEP_ORG_ID,
  },
};
