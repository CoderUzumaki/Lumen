"use client";

/**
 * Typed API client + TanStack Query hooks for /api/news/clusters/{id}/impact.
 *
 * The impact endpoint has three distinct outcomes and we use `apiFetchRaw` so
 * we can branch on `res.status` before parsing:
 *   - 200 → `ImpactRead` (cached assessment; return immediately)
 *   - 202 → `{ status: "generating", poll_url }` (async enqueue kicked off;
 *           caller should poll until 200 or give up after ~60s)
 *   - 404 → below threshold / cluster unknown / no active portfolio
 *
 * `useClusterImpact` handles the polling loop transparently: while the server
 * reports `generating`, the query refetches every 3s until either a cached
 * impact lands or `POLL_TIMEOUT_MS` elapses (`isPollTimedOut` on the returned
 * shape flips true so the UI can show the "still generating" message).
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
	useMutation,
	useQuery,
	useQueryClient,
	type UseMutationOptions,
} from "@tanstack/react-query";

import { apiFetchRaw } from "@/lib/api/client";

// ---------------------------------------------------------------------------
// Types — mirror `backend/app/schemas/impact.py`. Decimals arrive as strings.
// ---------------------------------------------------------------------------

export type Citation = {
	source: string;
	url: string;
	title: string;
	quote: string;
};

export type HistoricalAnalog = {
	event_description: string;
	when: string;
	outcome_description: string;
	similarity_score: number;
};

export type ImpactRead = {
	id: string;
	cluster_id: string;
	user_id: string;
	portfolio_id: string;
	mechanism: string;
	magnitude_low: string | null;
	magnitude_high: string | null;
	timeframe_days: number | null;
	confidence: string;
	falsifiability: string;
	citations: Citation[];
	historical_analogs: HistoricalAnalog[];
	affected_positions: string[];
	langsmith_run_id: string | null;
	created_at: string;
};

export type ImpactGenerating = { status: "generating"; poll_url: string };

/** Outcome of one impact fetch — the raw envelope our components consume. */
export type ImpactState =
	| { status: "cached"; impact: ImpactRead }
	| { status: "generating"; pollUrl: string }
	| { status: "not_found"; detail: string };

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const impactKeys = {
	all: ["impact"] as const,
	cluster: (id: string) => ["impact", "cluster", id] as const,
};

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function fetchImpact(clusterId: string): Promise<ImpactState> {
	const res = await apiFetchRaw(`/api/news/clusters/${clusterId}/impact`);
	if (res.status === 200) {
		const impact = (await res.json()) as ImpactRead;
		return { status: "cached", impact };
	}
	if (res.status === 202) {
		const body = (await res.json()) as ImpactGenerating;
		return { status: "generating", pollUrl: body.poll_url };
	}
	if (res.status === 404) {
		let detail = "Impact assessment unavailable.";
		try {
			const body = (await res.json()) as { detail?: string };
			if (body?.detail) detail = body.detail;
		} catch {
			// non-JSON body — fall through with default detail
		}
		return { status: "not_found", detail };
	}
	// Unexpected — surface as an error so react-query's `error` fires.
	let detail: string | undefined;
	try {
		const body = (await res.json()) as {
			error?: { message?: string };
			detail?: string;
		};
		detail = body?.error?.message ?? body?.detail;
	} catch {
		// no body
	}
	throw new Error(
		`GET /api/news/clusters/${clusterId}/impact → ${res.status}${
			detail ? `: ${detail}` : ""
		}`,
	);
}

async function requestImpactRegen(clusterId: string): Promise<ImpactGenerating> {
	const res = await apiFetchRaw(
		`/api/news/clusters/${clusterId}/impact/generate`,
		{ method: "POST" },
	);
	if (res.status === 202) {
		return (await res.json()) as ImpactGenerating;
	}
	let detail: string | undefined;
	try {
		const body = (await res.json()) as {
			error?: { message?: string };
			detail?: string;
		};
		detail = body?.error?.message ?? body?.detail;
	} catch {
		// no body
	}
	throw new Error(
		`POST /api/news/clusters/${clusterId}/impact/generate → ${res.status}${
			detail ? `: ${detail}` : ""
		}`,
	);
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

/**
 * How long we'll keep polling while the server says "generating" before
 * giving up and showing a "refresh in a bit" message. 60s per spec.
 */
export const POLL_TIMEOUT_MS = 60_000;
const POLL_INTERVAL_MS = 3_000;

/**
 * Fetch (and, while pending, auto-poll) the impact assessment for a cluster.
 *
 * Callers get:
 *   - `data`   — an `ImpactState` describing what we saw last
 *   - `isPollTimedOut` — true once we've been in `generating` for >60s
 *   - `error`  — any unexpected non-200/202/404 surfaced by react-query
 */
export function useClusterImpact(clusterId: string | undefined) {
	// Track when the current "generating" run started so we can time it out
	// after POLL_TIMEOUT_MS. Reset on cluster change or when a non-generating
	// state lands.
	const pollStartRef = useRef<number | null>(null);
	const [pollTimedOut, setPollTimedOut] = useState(false);

	const query = useQuery({
		queryKey: clusterId
			? impactKeys.cluster(clusterId)
			: ["impact", "cluster", "__missing__"],
		queryFn: () => fetchImpact(clusterId!),
		enabled: Boolean(clusterId),
		// Only poll while we're in the "generating" state and haven't timed out.
		refetchInterval: (q) => {
			const data = q.state.data as ImpactState | undefined;
			if (!data) return false;
			if (data.status !== "generating") return false;
			if (pollStartRef.current === null) return false;
			if (Date.now() - pollStartRef.current > POLL_TIMEOUT_MS) return false;
			return POLL_INTERVAL_MS;
		},
	});

	// Update timeout state as data flips between statuses.
	useEffect(() => {
		if (!query.data) return;
		if (query.data.status === "generating") {
			if (pollStartRef.current === null) {
				pollStartRef.current = Date.now();
				setPollTimedOut(false);
			} else if (Date.now() - pollStartRef.current > POLL_TIMEOUT_MS) {
				setPollTimedOut(true);
			}
		} else {
			pollStartRef.current = null;
			setPollTimedOut(false);
		}
	}, [query.data, query.dataUpdatedAt]);

	// Watchdog: even if react-query stops refetching, promote the UI to
	// "timed out" once the deadline passes.
	useEffect(() => {
		if (!query.data || query.data.status !== "generating") return;
		if (pollStartRef.current === null) return;
		const remaining = POLL_TIMEOUT_MS - (Date.now() - pollStartRef.current);
		if (remaining <= 0) {
			setPollTimedOut(true);
			return;
		}
		const t = window.setTimeout(() => setPollTimedOut(true), remaining);
		return () => window.clearTimeout(t);
	}, [query.data, query.dataUpdatedAt]);

	const refetch = query.refetch;
	const resetPoll = useCallback(() => {
		pollStartRef.current = null;
		setPollTimedOut(false);
	}, []);

	return {
		data: query.data,
		error: query.error,
		isLoading: query.isLoading,
		isFetching: query.isFetching,
		isPollTimedOut: pollTimedOut,
		refetch,
		resetPoll,
	};
}

/**
 * Trigger a fresh impact-assessment run. Backend enqueues async and returns
 * 202; on success we invalidate the cached impact query so the polling loop
 * picks up "generating" and waits for the new artifact.
 */
export function useRegenerateImpact(
	options?: UseMutationOptions<ImpactGenerating, Error, string>,
) {
	const qc = useQueryClient();
	return useMutation({
		mutationFn: (clusterId: string) => requestImpactRegen(clusterId),
		onSuccess: (...args) => {
			const clusterId = args[1] as string;
			qc.invalidateQueries({ queryKey: impactKeys.cluster(clusterId) });
			(options?.onSuccess as ((...a: unknown[]) => unknown) | undefined)?.(
				...args,
			);
		},
		...options,
	});
}
