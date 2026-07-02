"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { AuthProvider } from "@/components/auth/auth-provider";
import { ThemeProvider } from "@/components/theme-provider";

/**
 * Client-only provider stack. Server Components (like `app/layout.tsx`) import
 * this and wrap children with it. Order:
 *   ThemeProvider  – pins dark theme.
 *   QueryClient    – TanStack Query for server-state caching.
 *   AuthProvider   – Supabase session + user, exposed via `useAuth()`.
 *
 * The `useState` around `QueryClient` guarantees one client per browser tab,
 * shared across renders. Without it Fast Refresh would drop the cache.
 */
export function Providers({ children }: { children: ReactNode }) {
	const [queryClient] = useState(
		() =>
			new QueryClient({
				defaultOptions: {
					queries: {
						staleTime: 60_000,
						refetchOnWindowFocus: false,
					},
				},
			}),
	);

	return (
		<ThemeProvider>
			<QueryClientProvider client={queryClient}>
				<AuthProvider>{children}</AuthProvider>
			</QueryClientProvider>
		</ThemeProvider>
	);
}
