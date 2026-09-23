"use client";

import { Suspense } from "react";
import SignInContent from "./signin-content";

export default function SignInPage() {
	return (
		<Suspense
			fallback={
				<div className="flex min-h-screen items-center justify-center bg-black text-white">
					Loading...
				</div>
			}
		>
			<SignInContent />
		</Suspense>
	);
}
