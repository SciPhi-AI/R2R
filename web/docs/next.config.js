const withNextra = require('nextra')({
  theme: 'nextra-theme-docs',
  themeConfig: './theme.config.tsx',
})

module.exports = withNextra({
  basePath: '/docs',
  reactStrictMode: false,
  images: {
    domains: ['github.com', 'lh3.googleusercontent.com'],
  },
})