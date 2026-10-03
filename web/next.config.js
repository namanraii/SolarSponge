/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    return [{ source: "/api-proxy/:path*", destination: `${api}/:path*` }];
  },
};
module.exports = nextConfig;
