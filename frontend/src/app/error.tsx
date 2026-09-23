"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function Error({
	error,
	reset,
}: {
	error: Error & { digest?: string };
	reset: () => void;
}) {
	return (
		<div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-gray-50 px-4 text-center">
			<h1 className="text-2xl font-semibold text-gray-900">
				Something went wrong
			</h1>
			<p className="max-w-md text-gray-600">
				We hit an unexpected error. You can try again or return to the
				dashboard.
			</p>
			<div className="flex gap-3">
				<Button onClick={() => reset()}>Try again</Button>
				<Button variant="outline" asChild>
					<Link href="/dashboard">Go to dashboard</Link>
				</Button>
			</div>
		</div>
	);
}
