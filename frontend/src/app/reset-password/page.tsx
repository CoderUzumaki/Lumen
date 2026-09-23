"use client";

import { useState, type FormEvent } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { KeyRound, Loader2 } from "lucide-react";

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

const MIN_PASSWORD_LENGTH = 8;

// Landing page for the link in Supabase's password-reset email. The Supabase
// client reads the recovery token from the URL on load and opens a session,
// which AuthProvider exposes as `user`; with that session we can set a new
// password via updateUser().
export default function ResetPasswordPage() {
	const router = useRouter();
	const { loading, user } = useAuth();
	const [password, setPassword] = useState("");
	const [confirm, setConfirm] = useState("");
	const [submitting, setSubmitting] = useState(false);
	const [error, setError] = useState<string | null>(null);

	const handleSubmit = async (e: FormEvent<HTMLFormElement>) => {
		e.preventDefault();
		setError(null);

		if (password.length < MIN_PASSWORD_LENGTH) {
			setError(`Use at least ${MIN_PASSWORD_LENGTH} characters.`);
			return;
		}
		if (password !== confirm) {
			setError("The two passwords don't match.");
			return;
		}

		setSubmitting(true);
		try {
			const { error: updateError } = await getSupabaseBrowserClient().auth.updateUser({
				password,
			});
			if (updateError) throw updateError;
			router.replace("/dashboard");
		} catch (err) {
			setError(err instanceof Error ? err.message : "Couldn't update your password.");
			setSubmitting(false);
		}
	};

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
							<KeyRound className="h-6 w-6" />
						</div>
						<div className="space-y-2">
							<CardTitle className="text-3xl font-semibold text-white">
								Set a new password
							</CardTitle>
							<CardDescription className="text-base text-white/75">
								{loading
									? "Checking your reset link..."
									: user
									  ? `Choose a new password for ${user.email ?? "your account"}.`
									  : "This reset link is invalid or has expired."}
							</CardDescription>
						</div>
					</CardHeader>

					<CardContent className="space-y-6">
						{loading ? (
							<div className="flex justify-center py-4">
								<Loader2 className="h-6 w-6 animate-spin" />
							</div>
						) : user ? (
							<form onSubmit={handleSubmit} className="space-y-4">
								<div className="space-y-2">
									<Label htmlFor="new-password" className="text-white/85">
										New password
									</Label>
									<Input
										id="new-password"
										type="password"
										required
										minLength={MIN_PASSWORD_LENGTH}
										autoComplete="new-password"
										placeholder={`At least ${MIN_PASSWORD_LENGTH} characters`}
										value={password}
										onChange={(e) => setPassword(e.target.value)}
										className={inputClass}
									/>
								</div>
								<div className="space-y-2">
									<Label htmlFor="confirm-password" className="text-white/85">
										Confirm new password
									</Label>
									<Input
										id="confirm-password"
										type="password"
										required
										autoComplete="new-password"
										value={confirm}
										onChange={(e) => setConfirm(e.target.value)}
										className={inputClass}
									/>
								</div>
								<Button
									type="submit"
									disabled={submitting}
									size="lg"
									className="w-full rounded-xl bg-white text-black hover:bg-gray-100"
								>
									{submitting ? (
										<>
											<Loader2 className="h-4 w-4 animate-spin" />
											Saving...
										</>
									) : (
										"Update password"
									)}
								</Button>
							</form>
						) : (
							<Button
								asChild
								size="lg"
								className="w-full rounded-xl bg-white text-black hover:bg-gray-100"
							>
								<Link href="/signin?mode=reset">Request a new reset link</Link>
							</Button>
						)}

						{error ? (
							<div
								role="alert"
								className="rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100"
							>
								{error}
							</div>
						) : null}
					</CardContent>
				</Card>
			</div>
		</div>
	);
}
