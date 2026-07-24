"use client";

/**
 * Typed API client + TanStack Query hooks for /api/briefings.
 *
 * The SSE side of the endpoint (`/api/briefings/stream`) is consumed via
 * `useSse` in `@/hooks/use-sse` — this file covers only the JSON endpoints.
 *
 * `apiFetch` throws on non-2xx, but the "latest" endpoint legitimately returns
 * 404 when the user has no briefings yet. `useLatestBriefing` catches that
 * specific case and resolves to `null` so the UI can render an empty-state
 * without treating it as an error. All other errors still surface as
 * `query.error`.
 */
import {
	useMutation,
	useQuery,
	useQueryClient,
	type UseMutationOptions,
} from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";

// ---------------------------------------------------------------------------
// Types — mirror `backend/app/schemas/briefing.py`.
// ---------------------------------------------------------------------------

export type BriefingItem = {
	impact_id: string; // UUID
	cluster_title: string;
	one_line_summary: string;
	affected_positions: string[]; // e.g. ["NVDA", "AAPL"]
	mechanism_summary: string;
	confidence: number; // 0..1
};

export type BriefingContent = {
	top_movers: BriefingItem[]; // <= 5
	watchlist: BriefingItem[]; // <= 5
	what_would_change_my_thinking: string[]; // <= 5
	generated_summary: string;
};

export type BriefingRead = {
	id: string;
	user_id: string;
	portfolio_id: string;
	briefing_date: string; // YYYY-MM-DD
	structured_content: BriefingContent;
	cited_impact_ids: string[];
	generated_at: string;
	generation_duration_ms: number | null;
	langsmith_run_id: string | null;
};

export type BriefingRegenerateResponse = {
	status: "generating";
	poll_url: string;
};

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const briefingKeys = {
	all: ["briefings"] as const,
	latest: () => [...briefingKeys.all, "latest"] as const,
	byDate: (d: string) => [...briefingKeys.all, "date", d] as const,
};

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

/**
 * Returns the caller's most recent briefing, or `null` if none exist yet.
 * A 404 from the backend is folded into `data === null` so the page can
 * branch on empty state without treating it as an error.
 */
export function useLatestBriefing(options?: { enabled?: boolean }) {
	return useQuery<BriefingRead | null>({
		queryKey: briefingKeys.latest(),
		queryFn: async () => {
			try {
				return await apiFetch<BriefingRead>("/api/briefings/latest");
			} catch (err) {
				if (err instanceof Error && err.message.includes("404")) {
					return null;
				}
				throw err;
			}
		},
		enabled: options?.enabled,
	});
}

export function useBriefingByDate(
	date: string | undefined,
	options?: { enabled?: boolean },
) {
	return useQuery<BriefingRead | null>({
		queryKey: date
			? briefingKeys.byDate(date)
			: [...briefingKeys.all, "date", "__missing__"],
		queryFn: async () => {
			try {
				return await apiFetch<BriefingRead>(
					`/api/briefings?date=${encodeURIComponent(date!)}`,
				);
			} catch (err) {
				if (err instanceof Error && err.message.includes("404")) {
					return null;
				}
				throw err;
			}
		},
		enabled: Boolean(date) && options?.enabled !== false,
	});
}

// ---------------------------------------------------------------------------
// Regenerate (async POST → poll `/latest` until briefing_date advances)
// ---------------------------------------------------------------------------

export function useRegenerateBriefing(
	options?: UseMutationOptions<BriefingRegenerateResponse, Error, void>,
) {
	const qc = useQueryClient();
	return useMutation({
		mutationFn: () =>
			apiFetch<BriefingRegenerateResponse>("/api/briefings/regenerate", {
				method: "POST",
			}),
		onSuccess: (...args) => {
			qc.invalidateQueries({ queryKey: briefingKeys.all });
			// Forward v5-style tuple to any user-provided handler.
			(options?.onSuccess as ((...a: unknown[]) => unknown) | undefined)?.(
				...args,
			);
		},
		...options,
	});
}
