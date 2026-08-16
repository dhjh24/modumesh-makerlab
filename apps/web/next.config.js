/** @type {import('next').NextConfig} */
const apiInternal = process.env.API_INTERNAL_URL || 'http://localhost:8000';

const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  transpilePackages: ['@modumesh/ui', '@modumesh/viewer', '@modumesh/shared-types'],
  // Maker Studio IA (approved): /studio/* (editor), /explore (maker tools),
  // /admin/health (ops). Old routes 301 so nothing 404s during the transition.
  async redirects() {
    return [
      {
        source: '/projects/:id/compare',
        destination: '/studio/:id/compare',
        permanent: true,
      },
      {
        source: '/projects/:id',
        destination: '/studio/:id',
        permanent: true,
      },
      {
        source: '/generators/:plugin',
        destination: '/explore/:plugin',
        permanent: true,
      },
      {
        source: '/generators',
        destination: '/explore',
        permanent: true,
      },
      {
        source: '/health',
        destination: '/admin/health',
        permanent: true,
      },
    ];
  },
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiInternal}/api/v1/:path*`,
      },
      {
        source: '/backend-health',
        destination: `${apiInternal}/health`,
      },
      {
        source: '/backend-health/:path*',
        destination: `${apiInternal}/health/:path*`,
      },
      {
        source: '/health/:path*',
        destination: `${apiInternal}/health/:path*`,
      },
    ];
  },
};

module.exports = nextConfig;
