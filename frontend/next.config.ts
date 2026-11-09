import type { NextConfig } from "next";

// The rewrite keeps the browser same-origin: cookies stay first-party and no CORS
// configuration is needed in either environment.
const backendUrl = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendUrl}/api/:path*`,
      },
    ];
  },

  // Old routes from the pre-department-first console.
  async redirects() {
    return [
      { source: "/admin", destination: "/departments", permanent: false },
      {
        source: "/admin/departments",
        destination: "/departments",
        permanent: false,
      },
      {
        source: "/admin/access",
        destination: "/departments",
        permanent: false,
      },
      {
        source: "/admin/users",
        destination: "/settings/users",
        permanent: false,
      },
      {
        source: "/admin/organisation",
        destination: "/settings/organisation",
        permanent: false,
      },
      {
        source: "/admin/audit",
        destination: "/settings/audit",
        permanent: false,
      },
      {
        source: "/admin/connectors",
        destination: "/data/connectors",
        permanent: false,
      },
      {
        source: "/admin/data-sources",
        destination: "/data/sources",
        permanent: false,
      },
      {
        source: "/admin/mail/settings",
        destination: "/mail/settings",
        permanent: false,
      },
      {
        source: "/admin/mail/templates",
        destination: "/mail/templates",
        permanent: false,
      },
      {
        source: "/admin/mail/executions",
        destination: "/mail/executions",
        permanent: false,
      },
      {
        source: "/admin/mail/schedules",
        destination: "/departments",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
