import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function NotFound() {
	return (
		<div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-gray-50 px-4 text-center">
			<h1 className="text-2xl font-semibold text-gray-900">
				Page not found
			</h1>
			<p className="max-w-md text-gray-600">
				The page you are looking for does not exist or has been moved.
			</p>
			<Button asChild>
				<Link href="/">Back to home</Link>
			</Button>
		</div>
	);
}
