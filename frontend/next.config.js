/** @type {import('next').NextConfig} */

// Fail fast if a required public env var is missing. This runs at build time
// (next build) and at dev-server start (next dev), so a missing var blocks
// both rather than silently shipping with `undefined` baked into the bundle.
const requiredPublic = ["NEXT_PUBLIC_BACKEND_URL"];

const missing = requiredPublic.filter((name) => !process.env[name]);
if (missing.length > 0) {
	throw new Error(
		`Missing required environment variable(s): ${missing.join(", ")}. ` +
			`Copy frontend/.env.example to frontend/.env.local and fill in the values.`
	);
}

const nextConfig = {
	reactStrictMode: true,
};

module.exports = nextConfig;
