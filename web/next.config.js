module.exports = {
  reactStrictMode: false,
  images: {
    domains: ['github.com', 'lh3.googleusercontent.com'],
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'r2r-cloud-docs.vercel.app',
        port: '',
        pathname: '/**',
      },
    ],
  },

  async rewrites() {
    return [
      {
        source: '/docs',
        destination: 'https://r2r-cloud-docs.vercel.app/',
      },
      {
        source: '/docs/:path*',
        destination: 'https://r2r-cloud-docs.vercel.app/:path*',
      },
    ];
  },
};