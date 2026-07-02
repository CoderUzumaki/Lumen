"use client";

import { Suspense, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
	AlertCircle,
	ArrowRight,
	Home,
	LayoutDashboard,
	Loader2,
	ShieldAlert,
} from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

// Next 15 requires useSearchParams() to be under a Suspense boundary at
// prerender time. Wrapping the inner client component keeps the existing auth
// flow untouched while satisfying the framework.
export default function SignInPage() {
	return (
		<Suspense fallback={null}>
			<SignInInner />
		</Suspense>
	);
}

function SignInInner() {
	const router = useRouter();
	const searchParams = useSearchParams();
	const { loading, user } = useAuth();
	const [isStartingAuth, setIsStartingAuth] = useState(false);
	const [authError, setAuthError] = useState<string | null>(null);

	useEffect(() => {
		if (!loading && user) {
			const next = searchParams.get("next");
			router.replace(next && next.startsWith("/") ? next : "/dashboard");
		}
	}, [loading, router, searchParams, user]);

	const reasonCopy = useMemo(() => {
		const reason = searchParams.get("reason");

		if (reason === "expired") {
			return "Your session expired. Sign in again to continue.";
		}

		if (reason === "unauthorized") {
			return "You need to sign in before accessing that page.";
		}

		return "Your session is missing or no longer valid. Use the options below to continue.";
	}, [searchParams]);

	const handleGoogleSignIn = async () => {
		setIsStartingAuth(true);
		setAuthError(null);

		try {
			const supabase = getSupabaseBrowserClient();
			const redirectTo = `${window.location.origin}/signin${
				searchParams.get("next")
					? `?next=${encodeURIComponent(searchParams.get("next") as string)}`
					: ""
			}`;
			const { error } = await supabase.auth.signInWithOAuth({
				provider: "google",
				options: {
					redirectTo,
				},
			});
			if (error) {
				throw error;
			}
		} catch (error) {
			console.error("Failed to start sign-in flow:", error);
			const message =
				error instanceof Error
					? error.message
					: "Check your Supabase public URL/key and Google OAuth redirect settings.";
			setAuthError(
				`Couldn't start Google sign-in. ${message}`
			);
			setIsStartingAuth(false);
		}
	};

	if (loading) {
		return (
			<div className="min-h-screen bg-black text-white relative overflow-hidden">
				<div className="relative z-10 flex min-h-screen items-center justify-center px-4">
					<div className="flex items-center gap-3 rounded-full border border-white/15 bg-white/10 px-5 py-3 backdrop-blur-md">
						<Loader2 className="h-5 w-5 animate-spin" />
						<span className="text-sm text-white/90">
							Checking your session...
						</span>
					</div>
				</div>
			</div>
		);
	}

	return (
		<div className="min-h-screen bg-black text-white relative overflow-hidden">
			<div className="relative z-10 flex min-h-screen items-center justify-center px-4 py-10">
				<Card className="w-full max-w-lg border-white/15 bg-white/10 text-white shadow-2xl backdrop-blur-xl">
					<CardHeader className="space-y-4">
						<div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/15 bg-white/10">
							<ShieldAlert className="h-6 w-6" />
						</div>
						<div className="space-y-2">
							<CardTitle className="text-3xl font-semibold text-white">
								Sign in to continue
							</CardTitle>
							<CardDescription className="text-base text-white/75">
								{reasonCopy}
							</CardDescription>
						</div>
					</CardHeader>

					<CardContent className="space-y-6">
						<div className="rounded-2xl border border-white/10 bg-black/20 p-4">
							<div className="flex gap-3">
								<AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-white/80" />
								<div className="space-y-1 text-sm text-white/75">
									<p className="font-medium text-white">
										Authentication flow
									</p>
									<p>
										Lumen now signs users in through Supabase on the frontend and
										sends the resulting access token to the Flask API. If the
										button below fails, the usual cause is missing Supabase env
										variables or an OAuth redirect URL that has not been added in
										the Supabase dashboard.
									</p>
								</div>
							</div>
						</div>

						<div className="space-y-3">
							<Button
								onClick={handleGoogleSignIn}
								disabled={isStartingAuth}
								size="lg"
								className="w-full rounded-xl bg-white text-black hover:bg-gray-100"
							>
								{isStartingAuth ? (
									<>
										<Loader2 className="h-4 w-4 animate-spin" />
										Starting Google sign-in...
									</>
								) : (
									<>
										Continue with Google
										<ArrowRight className="h-4 w-4" />
									</>
								)}
							</Button>

							<div className="grid gap-3 sm:grid-cols-2">
								<Button
									asChild
									variant="outline"
									size="lg"
									className="rounded-xl border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
								>
									<Link href="/">
										<Home className="h-4 w-4" />
										Back to home
									</Link>
								</Button>

								<Button
									asChild
									variant="outline"
									size="lg"
									className="rounded-xl border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
								>
									<Link href="/dashboard">
										<LayoutDashboard className="h-4 w-4" />
										Open dashboard
									</Link>
								</Button>
							</div>
						</div>

						{authError ? (
							<div className="rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100">
								{authError}
							</div>
						) : null}
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
