import type { NextConfig } from 'next';

const apiTarget = process.env.AGENTSHIELD_API_URL ?? 'http://localhost:8000';

const nextConfig: NextConfig = {
  output: 'standalone',
  async rewrites() {
    return [
      {
        source: '/api/v1/:path*',
        destination: `${apiTarget}/api/v1/:path*`,
      },
      {
        source: '/health/:path*',
        destination: `${apiTarget}/health/:path*`,
      },
    ];
  },
};

export default nextConfig;
