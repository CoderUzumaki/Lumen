"use client";

import { useEffect, useMemo, useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
	ArrowRight,
	Home,
	LayoutDashboard,
	Loader2,
	ShieldAlert,
} from "lucide-react";

import { useAuth } from "@/components/auth/auth-provider";
import Aurora from "@/components/landing/Aurora";
import { Button } from "@/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { getSupabaseBrowserClient } from "@/lib/supabase/client";

type Mode = "signin" | "signup" | "reset";

const MIN_PASSWORD_LENGTH = 8;

// Only allow same-origin relative paths. "//host" and "/\host" are treated by
// browsers as protocol-relative URLs and would redirect off-site.
function safeNextPath(next: string | null): string {
	if (!next || !next.startsWith("/")) return "/dashboard";
	if (next.startsWith("//") || next.startsWith("/\\")) return "/dashboard";
	return next;
}

function friendlyAuthError(message: string): string {
	if (/email not confirmed/i.test(message)) {
		return "Confirm your email first. Check your inbox for the confirmation link.";
	}
	if (/invalid login credentials/i.test(message)) {
		return "That email and password don't match. Try again or reset your password.";
	}
	return message;
}

export default function SignInContent() {
	const router = useRouter();
	const searchParams = useSearchParams();
	const { loading, user } = useAuth();

	const next = safeNextPath(searchParams.get("next"));
	const [mode, setMode] = useState<Mode>(
		searchParams.get("mode") === "reset" ? "reset" : "signin"
	);
	const [email, setEmail] = useState("");
	const [password, setPassword] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [isStartingGoogle, setIsStartingGoogle] = useState(false);
	const [authError, setAuthError] = useState<string | null>(null);
	const [notice, setNotice] = useState<string | null>(null);

	useEffect(() => {
		if (!loading && user) {
			router.replace(next);
		}
	}, [loading, next, router, user]);

	const reasonCopy = useMemo(() => {
		const reason = searchParams.get("reason");
		if (reason === "expired") {
			return "Your session expired. Sign in again to continue.";
		}
		if (reason === "unauthorized") {
			return "You need to sign in before accessing that page.";
		}
		return "Sign in to access your invoices and analytics.";
	}, [searchParams]);

	const title =
		mode === "signup"
			? "Create your account"
			: mode === "reset"
			  ? "Reset your password"
			  : "Sign in to continue";

	const switchMode = (nextMode: Mode) => {
		setMode(nextMode);
		setAuthError(null);
		setNotice(null);
	};

	// Where Supabase sends the user back after clicking an email link. It must
	// be listed under Auth -> URL Configuration -> Redirect URLs in Supabase.
	const signInReturnUrl = () =>
		`${window.location.origin}/signin?next=${encodeURIComponent(next)}`;

	const handleEmailSubmit = async (e: FormEvent<HTMLFormElement>) => {
		e.preventDefault();
		setAuthError(null);
		setNotice(null);
		setSubmitting(true);

		try {
			const supabase = getSupabaseBrowserClient();

			if (mode === "signin") {
				const { error } = await supabase.auth.signInWithPassword({
					email,
					password,
				});
				if (error) throw error;
				// AuthProvider picks up the new session and the effect above redirects.
			} else if (mode === "signup") {
				const { data, error } = await supabase.auth.signUp({
					email,
					password,
					options: { emailRedirectTo: signInReturnUrl() },
				});
				if (error) throw error;
				if (!data.session) {
					// Email confirmation is on: no session until the link is clicked.
					setNotice(
						`We sent a confirmation link to ${email}. Open it to finish creating your account.`
					);
					setPassword("");
				}
			} else {
				const { error } = await supabase.auth.resetPasswordForEmail(email, {
					redirectTo: `${window.location.origin}/reset-password`,
				});
				if (error) throw error;
				// Same message whether or not the account exists (no user enumeration).
				setNotice(
					`If an account exists for ${email}, a password reset link is on its way.`
				);
			}
		} catch (error) {
			const message =
				error instanceof Error ? error.message : "Something went wrong. Try again.";
			setAuthError(friendlyAuthError(message));
		} finally {
			setSubmitting(false);
		}
	};

	const handleGoogleSignIn = async () => {
		setIsStartingGoogle(true);
		setAuthError(null);
		setNotice(null);

		try {
			const supabase = getSupabaseBrowserClient();
			const { error } = await supabase.auth.signInWithOAuth({
				provider: "google",
				options: { redirectTo: signInReturnUrl() },
			});
			if (error) throw error;
		} catch (error) {
			console.error("Failed to start sign-in flow:", error);
			const message =
				error instanceof Error
					? error.message
					: "Check your Supabase and Google OAuth settings.";
			setAuthError(`Couldn't start Google sign-in. ${message}`);
			setIsStartingGoogle(false);
		}
	};

	if (loading) {
		return (
			<div className="min-h-screen bg-black text-white relative overflow-hidden">
				<div className="fixed inset-0">
					<Aurora
						colorStops={["#475569", "#64748b", "#475569"]}
						amplitude={1.2}
						blend={0.6}
						speed={0.8}
					/>
				</div>
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

	const inputClass =
		"h-11 rounded-xl border-white/20 bg-white/5 text-white placeholder:text-white/40 focus-visible:border-white/40 focus-visible:ring-white/20";

	return (
		<div className="min-h-screen bg-black text-white relative overflow-hidden">
			<div className="fixed inset-0">
				<Aurora
					colorStops={["#475569", "#64748b", "#475569"]}
					amplitude={1.2}
					blend={0.6}
					speed={0.8}
				/>
			</div>

			<div className="relative z-10 flex min-h-screen items-center justify-center px-4 py-10">
				<Card className="w-full max-w-lg border-white/15 bg-white/10 text-white shadow-2xl backdrop-blur-xl">
					<CardHeader className="space-y-4">
						<div className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/15 bg-white/10">
							<ShieldAlert className="h-6 w-6" />
						</div>
						<div className="space-y-2">
							<CardTitle className="text-3xl font-semibold text-white">
								{title}
							</CardTitle>
							<CardDescription className="text-base text-white/75">
								{mode === "reset"
									? "Enter your email and we'll send you a link to set a new password."
									: reasonCopy}
							</CardDescription>
						</div>
					</CardHeader>

					<CardContent className="space-y-6">
						<form onSubmit={handleEmailSubmit} className="space-y-4" noValidate={false}>
							<div className="space-y-2">
								<Label htmlFor="email" className="text-white/85">
									Email
								</Label>
								<Input
									id="email"
									type="email"
									required
									autoComplete="email"
									placeholder="you@company.com"
									value={email}
									onChange={(e) => setEmail(e.target.value)}
									className={inputClass}
								/>
							</div>

							{mode !== "reset" ? (
								<div className="space-y-2">
									<div className="flex items-center justify-between">
										<Label htmlFor="password" className="text-white/85">
											Password
										</Label>
										{mode === "signin" ? (
											<button
												type="button"
												onClick={() => switchMode("reset")}
												className="text-xs text-white/60 underline-offset-4 hover:text-white hover:underline"
											>
												Forgot password?
											</button>
										) : null}
									</div>
									<Input
										id="password"
										type="password"
										required
										minLength={mode === "signup" ? MIN_PASSWORD_LENGTH : undefined}
										autoComplete={
											mode === "signup" ? "new-password" : "current-password"
										}
										placeholder={
											mode === "signup"
												? `At least ${MIN_PASSWORD_LENGTH} characters`
												: "Your password"
										}
										value={password}
										onChange={(e) => setPassword(e.target.value)}
										className={inputClass}
									/>
								</div>
							) : null}

							<Button
								type="submit"
								disabled={submitting}
								size="lg"
								className="w-full rounded-xl bg-white text-black hover:bg-gray-100"
							>
								{submitting ? (
									<>
										<Loader2 className="h-4 w-4 animate-spin" />
										Please wait...
									</>
								) : mode === "signup" ? (
									"Create account"
								) : mode === "reset" ? (
									"Send reset link"
								) : (
									"Sign in"
								)}
							</Button>

							<p className="text-center text-sm text-white/60">
								{mode === "signin" ? (
									<>
										New to Lumen?{" "}
										<button
											type="button"
											onClick={() => switchMode("signup")}
											className="text-white underline-offset-4 hover:underline"
										>
											Create an account
										</button>
									</>
								) : (
									<>
										{mode === "signup" ? "Already have an account? " : "Remembered it? "}
										<button
											type="button"
											onClick={() => switchMode("signin")}
											className="text-white underline-offset-4 hover:underline"
										>
											Sign in
										</button>
									</>
								)}
							</p>
						</form>

						{notice ? (
							<div
								role="status"
								className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 p-3 text-sm text-emerald-100"
							>
								{notice}
							</div>
						) : null}

						{authError ? (
							<div
								role="alert"
								className="rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100"
							>
								{authError}
							</div>
						) : null}

						{mode !== "reset" ? (
							<>
								<div className="flex items-center gap-3 text-xs uppercase tracking-wider text-white/40">
									<span className="h-px flex-1 bg-white/15" />
									or
									<span className="h-px flex-1 bg-white/15" />
								</div>

								<Button
									type="button"
									onClick={handleGoogleSignIn}
									disabled={isStartingGoogle}
									variant="outline"
									size="lg"
									className="w-full rounded-xl border-white/20 bg-transparent text-white hover:bg-white/10 hover:text-white"
								>
									{isStartingGoogle ? (
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
							</>
						) : null}

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
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
