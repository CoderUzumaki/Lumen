"use client";

/**
 * Typed API client + TanStack Query hooks for /api/news/*.
 *
 * REL-07 (feed) uses `useNewsFeed`. IMP-06 (detail) uses `useClusterDetail`
 * plus `useClusterImpact` from `./impact.ts`.
 *
 * All requests attach the Supabase session bearer via `apiFetch`. Query keys
 * live under `["news", ...]` — invalidating the whole namespace refreshes
 * every feed and detail view mounted at the time.
 */

import { useQuery } from "@tanstack/react-query";

import { apiFetch } from "@/lib/api/client";

// ---------------------------------------------------------------------------
// Types — mirror `backend/app/schemas/news.py`. Decimals arrive as strings.
// ---------------------------------------------------------------------------

export type NewsSource = "newsapi" | "marketaux" | "gdelt" | "edgar" | "rss";

export type NewsItemRead = {
	id: string;
	cluster_id: string | null;
	source: NewsSource;
	source_id: string | null;
	url: string;
	url_hash: string;
	title: string;
	body: string | null;
	published_at: string;
	ingested_at: string;
};

export type NewsClusterRead = {
	id: string;
	canonical_title: string;
	canonical_summary: string | null;
	first_seen_at: string;
	last_seen_at: string;
	entity_tickers: string[];
	entity_topics: string[];
	authority_score: string;
	novelty_score: string;
	items: NewsItemRead[];
};

export type RelevanceRead = {
	id: string;
	cluster_id: string;
	user_id: string;
	portfolio_id: string;
	score: string;
	touched_position_ids: string[];
	touched_theme_ids: string[];
	stage: "prefilter" | "classifier";
	rationale: string | null;
	computed_at: string;
};

export type RelevantClusterRead = {
	cluster: NewsClusterRead;
	relevance: RelevanceRead;
};

export type ClusterDetailRead = {
	cluster: NewsClusterRead;
	relevance: RelevanceRead | null;
	// The cluster-detail endpoint embeds a cached impact-assessment row when one
	// exists. UI consumers read impact via `useClusterImpact` (impact.ts) rather
	// than this field, so we leave the shape opaque here to keep news.ts free of
	// a cross-module dependency on impact.ts.
	impact: unknown;
};

export type NewsFeedOptions = {
	limit?: number;
	since?: string;
};

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const newsKeys = {
	all: ["news"] as const,
	feed: (opts: NewsFeedOptions = {}) => ["news", "feed", opts] as const,
	cluster: (id: string) => ["news", "cluster", id] as const,
};

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

/**
 * Relevance-scored news feed for the caller's active portfolio.
 *
 * Backend returns `[]` if no portfolio is active — we don't distinguish that
 * from "no relevant clusters yet"; the empty-state copy covers both.
 */
export function useNewsFeed(opts: NewsFeedOptions = {}) {
	const query = new URLSearchParams();
	if (opts.limit !== undefined) query.set("limit", String(opts.limit));
	if (opts.since) query.set("since", opts.since);
	const suffix = query.toString();
	return useQuery({
		queryKey: newsKeys.feed(opts),
		queryFn: () =>
			apiFetch<RelevantClusterRead[]>(
				`/api/news/relevant${suffix ? `?${suffix}` : ""}`,
			),
	});
}

/**
 * Cluster detail — canonical title/summary + relevance + cached impact if any.
 * 404s when the cluster is unknown or belongs to no known ingest.
 */
export function useClusterDetail(id: string | undefined) {
	return useQuery({
		queryKey: id ? newsKeys.cluster(id) : ["news", "cluster", "__missing__"],
		queryFn: () => apiFetch<ClusterDetailRead>(`/api/news/clusters/${id!}`),
		enabled: Boolean(id),
	});
}

// ---------------------------------------------------------------------------
// Formatters — Decimals arrive as strings; consistent rendering lives here so
// feed rows and detail cards agree.
// ---------------------------------------------------------------------------

/** "0.435" → "43.5%". Returns "—" for invalid input. */
export function formatScorePercent(score: string | number | null | undefined): string {
	if (score === null || score === undefined) return "—";
	const n = typeof score === "number" ? score : Number(score);
	if (!Number.isFinite(n)) return "—";
	return `${(n * 100).toFixed(1)}%`;
}

/** Clamp a 0..1 score into a 0..100 percentage for progress-bar widths. */
export function scoreToPercent(score: string | number | null | undefined): number {
	if (score === null || score === undefined) return 0;
	const n = typeof score === "number" ? score : Number(score);
	if (!Number.isFinite(n)) return 0;
	return Math.max(0, Math.min(100, n * 100));
}

/**
 * Signed percent for a magnitude endpoint. `+7.0%`, `-3.0%`, or `—` when null.
 * Fractions: 0.03 → "+3.0%".
 */
export function formatSignedPercent(value: string | null | undefined): string {
	if (value === null || value === undefined) return "—";
	const n = Number(value);
	if (!Number.isFinite(n)) return "—";
	const pct = n * 100;
	const sign = pct > 0 ? "+" : pct < 0 ? "" : "";
	return `${sign}${pct.toFixed(1)}%`;
}

/** "2026-07-24T14:23:00Z" → "Jul 24, 2026". */
export function formatShortDate(iso: string | null | undefined): string {
	if (!iso) return "—";
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return "—";
	return d.toLocaleDateString(undefined, {
		year: "numeric",
		month: "short",
		day: "numeric",
	});
}

/** Human relative timestamp — "3h ago", "2d ago" — for feed row metadata. */
export function formatRelativeTime(iso: string | null | undefined): string {
	if (!iso) return "—";
	const d = new Date(iso);
	if (Number.isNaN(d.getTime())) return "—";
	const diffMs = Date.now() - d.getTime();
	const diffSec = Math.max(0, Math.floor(diffMs / 1000));
	if (diffSec < 60) return "just now";
	const diffMin = Math.floor(diffSec / 60);
	if (diffMin < 60) return `${diffMin}m ago`;
	const diffHr = Math.floor(diffMin / 60);
	if (diffHr < 24) return `${diffHr}h ago`;
	const diffDay = Math.floor(diffHr / 24);
	if (diffDay < 30) return `${diffDay}d ago`;
	return formatShortDate(iso);
}

/**
 * Below-threshold scores don't get an impact assessment written. The backend
 * cutoff currently sits at 0.3 — surface it in one place so the UI matches.
 */
export const IMPACT_MIN_SCORE = 0.3;

export function canHaveImpact(score: string | number | null | undefined): boolean {
	if (score === null || score === undefined) return false;
	const n = typeof score === "number" ? score : Number(score);
	if (!Number.isFinite(n)) return false;
	return n >= IMPACT_MIN_SCORE;
}
