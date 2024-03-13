module.exports = {
  reactStrictMode: false,
  images: {
    domains: ['github.com', 'lh3.googleusercontent.com'],
  },
  async rewrites() {
    return [
      {
        source: '/docs',
        destination: '/docs/index.html',
      },
      {
        source: '/docs/:path*',
        destination: '/docs/:path*.html',
      },
    ];
  },
};