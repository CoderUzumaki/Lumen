"use client";

import { useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Loader2, ShieldAlert } from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";

export function AuthGuard({ children }: { children: React.ReactNode }) {
	const router = useRouter();
	const pathname = usePathname();
	const searchParams = useSearchParams();
	const { loading, user } = useAuth();

	useEffect(() => {
		if (loading || user) {
			return;
		}

		const query = searchParams.toString();
		const next = query ? `${pathname}?${query}` : pathname;
		router.replace(`/signin?reason=unauthorized&next=${encodeURIComponent(next)}`);
	}, [loading, pathname, router, searchParams, user]);

	if (loading) {
		return (
			<div className="flex min-h-screen items-center justify-center bg-background px-4">
				<div className="flex items-center gap-3 rounded-full border bg-card px-5 py-3 shadow-sm">
					<Loader2 className="h-5 w-5 animate-spin" />
					<span className="text-sm text-muted-foreground">
						Checking your session...
					</span>
				</div>
			</div>
		);
	}

	if (!user) {
		return (
			<div className="flex min-h-screen items-center justify-center bg-background px-4">
				<div className="flex items-center gap-3 rounded-xl border bg-card px-5 py-4 shadow-sm">
					<ShieldAlert className="h-5 w-5" />
					<div>
						<p className="font-medium">Redirecting to sign in</p>
						<p className="text-sm text-muted-foreground">
							You need an authenticated session to view this page.
						</p>
					</div>
				</div>
			</div>
		);
	}

	return <>{children}</>;
}
