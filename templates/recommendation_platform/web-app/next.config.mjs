/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  serverRuntimeConfig: {
    api: {
      bodyParser: false,
      responseLimit: false,
    },
  },
};

export default nextConfig;
