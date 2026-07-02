import type { NextConfig } from "next";

// Fail fast if a required public env var is missing. Runs at build time
// (`next build`) and at dev-server start (`next dev`) so a missing var blocks
// both rather than silently baking `undefined` into the bundle.
const requiredPublic = [
	"NEXT_PUBLIC_BACKEND_URL",
	"NEXT_PUBLIC_SUPABASE_URL",
	"NEXT_PUBLIC_SUPABASE_ANON_KEY",
];

const missing = requiredPublic.filter((name) => !process.env[name]);
if (missing.length > 0) {
	throw new Error(
		`Missing required environment variable(s): ${missing.join(", ")}. ` +
			`Copy frontend/.env.example to frontend/.env.local and fill in the values.`,
	);
}

const nextConfig: NextConfig = {
	reactStrictMode: true,
};

export default nextConfig;
