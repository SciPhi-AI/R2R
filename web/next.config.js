const { DOCS_URL } = process.env;

/** @type {import('next').NextConfig} */
module.exports = {
  reactStrictMode: false,
  images: {
    domains: ['github.com', 'lh3.googleusercontent.com'],
  },
  async rewrites() {
    return [
      {
        source: "/docs",
        destination: `${DOCS_URL}/docs`,
      },
      {
        source: "/docs/:path*",
        destination: `${DOCS_URL}/docs/:path*`,
      },
    ];
  },
};
