/** @type {import('next').NextConfig} */
const apiInternal = process.env.API_INTERNAL_URL || 'http://localhost:8000';

const nextConfig = {
  output: 'standalone',
  reactStrictMode: true,
  transpilePackages: ['@modumesh/ui', '@modumesh/viewer', '@modumesh/shared-types'],
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
