"use client";

import dynamic from "next/dynamic";
import { Suspense } from "react";
import { AuthGuard } from "@/components/auth/auth-guard";

const DashboardContent = dynamic(() => import("./dashboardContent"), {
	ssr: false,
});

export default function DashboardPage() {
	return (
		<AuthGuard>
			<Suspense
				fallback={
					<div className="flex min-h-screen items-center justify-center">
						Loading...
					</div>
				}
			>
				<DashboardContent />
			</Suspense>
		</AuthGuard>
	);
}