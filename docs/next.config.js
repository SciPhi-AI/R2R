const withNextra = require('nextra')({
  theme: 'nextra-theme-docs',
  themeConfig: './theme.config.tsx',
})

module.exports = withNextra({
  basePath: '/docs',
  assetPrefix: '/docs',
}); // eslint-disable-line @typescript-eslint/no-var-requires