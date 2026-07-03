import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PROTECTED_PREFIXES = [
	"/dashboard",
	"/analytics",
	"/ai-analytics",
	"/chatbot",
	"/upload",
];

export function middleware(request: NextRequest) {
	const { pathname, search } = request.nextUrl;
	const isProtected = PROTECTED_PREFIXES.some(
		(prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
	);

	if (!isProtected) {
		return NextResponse.next();
	}

	const hasSession = request.cookies.get("lumen_session")?.value === "1";
	if (hasSession) {
		return NextResponse.next();
	}

	const signInUrl = new URL("/signin", request.url);
	signInUrl.searchParams.set("reason", "unauthorized");
	signInUrl.searchParams.set("next", `${pathname}${search}`);
	return NextResponse.redirect(signInUrl);
}

export const config = {
	matcher: [
		"/dashboard/:path*",
		"/analytics/:path*",
		"/ai-analytics/:path*",
		"/chatbot/:path*",
		"/upload/:path*",
	],
};
