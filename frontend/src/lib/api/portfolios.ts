"use client";

/**
 * Typed API client + TanStack Query hooks for /api/portfolios and /api/positions.
 *
 * All requests attach the current Supabase session's access token as a Bearer
 * — the backend (`app.utils.auth.require_auth`) verifies it against the
 * Supabase JWKS endpoint. Requests without a session throw, so callers must
 * be inside an `<AuthGuard>` boundary (see `app/portfolios/layout.tsx` etc.).
 *
 * Query keys are namespaced under `["portfolios", ...]` so a targeted
 * `invalidateQueries({ queryKey: ["portfolios"] })` after a mutation refreshes
 * every list/detail view mounted at the time.
 */
import {
	useMutation,
	useQuery,
	useQueryClient,
	type UseMutationOptions,
} from "@tanstack/react-query";

import { getSupabaseBrowserClient } from "@/lib/supabase/client";

// ---------------------------------------------------------------------------
// Types — mirror `backend/app/schemas/portfolio.py`.
// ---------------------------------------------------------------------------

export type AssetType = "equity" | "etf" | "crypto" | "bond" | "other";

export type Position = {
	id: string;
	portfolio_id: string;
	created_at: string;
	ticker: string;
	asset_type: AssetType;
	quantity: string | null;
	cost_basis: string | null;
	currency: string;
	exchange: string | null;
	notes: string | null;
};

export type Portfolio = {
	id: string;
	user_id: string;
	name: string;
	is_active: boolean;
	created_at: string;
	updated_at: string;
	positions: Position[];
};

export type PortfolioCreateInput = {
	name: string;
	is_active?: boolean;
};

export type PortfolioUpdateInput = Partial<PortfolioCreateInput>;

export type PositionCreateInput = {
	ticker: string;
	asset_type?: AssetType;
	quantity?: string | null;
	cost_basis?: string | null;
	currency?: string;
	exchange?: string | null;
	notes?: string | null;
};

export type PositionUpdateInput = Partial<PositionCreateInput>;

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

if (!BACKEND_URL) {
	// Fail fast at module load — next.config validates env at build time,
	// but a defensive check here catches misconfigured dev runs.
	console.warn(
		"NEXT_PUBLIC_BACKEND_URL is not set; portfolios API calls will fail.",
	);
}

async function currentAccessToken(): Promise<string> {
	const supabase = getSupabaseBrowserClient();
	const { data } = await supabase.auth.getSession();
	const token = data.session?.access_token;
	if (!token) {
		throw new Error("Not signed in — no Supabase session.");
	}
	return token;
}

async function apiFetch<T>(
	path: string,
	init: RequestInit & { parseJson?: boolean } = {},
): Promise<T> {
	const token = await currentAccessToken();
	const { parseJson = true, headers, ...rest } = init;
	const res = await fetch(`${BACKEND_URL}${path}`, {
		...rest,
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
			...headers,
		},
	});
	if (!res.ok) {
		let detail: string | undefined;
		try {
			const body = await res.json();
			detail = body?.error?.message ?? body?.detail;
		} catch {
			// non-JSON body — fall through
		}
		throw new Error(
			`API ${init.method ?? "GET"} ${path} → ${res.status}${
				detail ? `: ${detail}` : ""
			}`,
		);
	}
	if (!parseJson || res.status === 204) {
		// void — caller doesn't want a body (DELETE, etc.).
		return undefined as T;
	}
	return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const portfolioKeys = {
	all: ["portfolios"] as const,
	lists: () => [...portfolioKeys.all, "list"] as const,
	detail: (id: string) => [...portfolioKeys.all, "detail", id] as const,
	positions: (id: string) => [...portfolioKeys.all, "positions", id] as const,
};

// ---------------------------------------------------------------------------
// Reads
// ---------------------------------------------------------------------------

export function useListPortfolios(options?: { enabled?: boolean }) {
	return useQuery({
		queryKey: portfolioKeys.lists(),
		queryFn: () => apiFetch<Portfolio[]>("/api/portfolios"),
		enabled: options?.enabled,
	});
}

export function usePortfolio(id: string | undefined) {
	return useQuery({
		queryKey: id ? portfolioKeys.detail(id) : ["portfolios", "detail", "__missing__"],
		queryFn: () => apiFetch<Portfolio>(`/api/portfolios/${id!}`),
		enabled: Boolean(id),
	});
}

// ---------------------------------------------------------------------------
// Portfolio mutations
// ---------------------------------------------------------------------------

export function useCreatePortfolio(
	options?: UseMutationOptions<Portfolio, Error, PortfolioCreateInput>,
) {
	const qc = useQueryClient();
	return useMutation({
		mutationFn: (input: PortfolioCreateInput) =>
			apiFetch<Portfolio>("/api/portfolios", {
				method: "POST",
				body: JSON.stringify(input),
			}),
		onSuccess: (...args) => {
			qc.invalidateQueries({ queryKey: portfolioKeys.all });
			// Forward all args (data, variables, context, ...) so callers with
			// their own onSuccess handler get the full v5-style tuple.
			(options?.onSuccess as ((...a: unknown[]) => unknown) | undefined)?.(
				...args,
			);
		},
		...options,
	});
}

export function useUpdatePortfolio(
	options?: UseMutationOptions<
		Portfolio,
		Error,
		{ id: string; input: PortfolioUpdateInput }
	>,
) {
	const qc = useQueryClient();
	return useMutation({
		mutationFn: ({ id, input }) =>
			apiFetch<Portfolio>(`/api/portfolios/${id}`, {
				method: "PUT",
				body: JSON.stringify(input),
			}),
		onSuccess: (...args) => {
			qc.invalidateQueries({ queryKey: portfolioKeys.all });
			// Forward all args (data, variables, context, ...) so callers with
			// their own onSuccess handler get the full v5-style tuple.
			(options?.onSuccess as ((...a: unknown[]) => unknown) | undefined)?.(
				...args,
			);
		},
		...options,
	});
}

export function useDeletePortfolio(
	options?: UseMutationOptions<void, Error, string>,
) {
	const qc = useQueryClient();
	return useMutation({
		mutationFn: (id: string) =>
			apiFetch<void>(`/api/portfolios/${id}`, {
				method: "DELETE",
				parseJson: false,
			}),
		onSuccess: (...args) => {
			qc.invalidateQueries({ queryKey: portfolioKeys.all });
			// Forward all args (data, variables, context, ...) so callers with
			// their own onSuccess handler get the full v5-style tuple.
			(options?.onSuccess as ((...a: unknown[]) => unknown) | undefined)?.(
				...args,
			);
		},
		...options,
	});
}

export function useActivatePortfolio(
	options?: UseMutationOptions<Portfolio, Error, string>,
) {
	const qc = useQueryClient();
	return useMutation({
		mutationFn: (id: string) =>
			apiFetch<Portfolio>(`/api/portfolios/${id}/activate`, {
				method: "POST",
			}),
		onSuccess: (...args) => {
			qc.invalidateQueries({ queryKey: portfolioKeys.all });
			// Forward all args (data, variables, context, ...) so callers with
			// their own onSuccess handler get the full v5-style tuple.
			(options?.onSuccess as ((...a: unknown[]) => unknown) | undefined)?.(
				...args,
			);
		},
		...options,
	});
}

// ---------------------------------------------------------------------------
// Position mutations
// ---------------------------------------------------------------------------

export function useAddPosition(
	options?: UseMutationOptions<
		Position,
		Error,
		{ portfolioId: string; input: PositionCreateInput }
	>,
) {
	const qc = useQueryClient();
	return useMutation({
		mutationFn: ({ portfolioId, input }) =>
			apiFetch<Position>(`/api/portfolios/${portfolioId}/positions`, {
				method: "POST",
				body: JSON.stringify(input),
			}),
		onSuccess: (...args) => {
			qc.invalidateQueries({ queryKey: portfolioKeys.all });
			// Forward all args (data, variables, context, ...) so callers with
			// their own onSuccess handler get the full v5-style tuple.
			(options?.onSuccess as ((...a: unknown[]) => unknown) | undefined)?.(
				...args,
			);
		},
		...options,
	});
}

export function useUpdatePosition(
	options?: UseMutationOptions<
		Position,
		Error,
		{ positionId: string; input: PositionUpdateInput }
	>,
) {
	const qc = useQueryClient();
	return useMutation({
		mutationFn: ({ positionId, input }) =>
			apiFetch<Position>(`/api/positions/${positionId}`, {
				method: "PUT",
				body: JSON.stringify(input),
			}),
		onSuccess: (...args) => {
			qc.invalidateQueries({ queryKey: portfolioKeys.all });
			// Forward all args (data, variables, context, ...) so callers with
			// their own onSuccess handler get the full v5-style tuple.
			(options?.onSuccess as ((...a: unknown[]) => unknown) | undefined)?.(
				...args,
			);
		},
		...options,
	});
}

export function useDeletePosition(
	options?: UseMutationOptions<void, Error, string>,
) {
	const qc = useQueryClient();
	return useMutation({
		mutationFn: (positionId: string) =>
			apiFetch<void>(`/api/positions/${positionId}`, {
				method: "DELETE",
				parseJson: false,
			}),
		onSuccess: (...args) => {
			qc.invalidateQueries({ queryKey: portfolioKeys.all });
			// Forward all args (data, variables, context, ...) so callers with
			// their own onSuccess handler get the full v5-style tuple.
			(options?.onSuccess as ((...a: unknown[]) => unknown) | undefined)?.(
				...args,
			);
		},
		...options,
	});
}

// ---------------------------------------------------------------------------
// Sample portfolio helper
// ---------------------------------------------------------------------------

/**
 * The seed portfolio a recruiter-visible "Load sample" button drops into the
 * onboarding form. Plausible tech-heavy US portfolio. Tickers only — no
 * quantities / cost basis (users can fill those in later).
 */
export const SAMPLE_PORTFOLIO_TICKERS: readonly PositionCreateInput[] = [
	{ ticker: "AAPL", asset_type: "equity", currency: "USD", exchange: "NASDAQ" },
	{ ticker: "MSFT", asset_type: "equity", currency: "USD", exchange: "NASDAQ" },
	{ ticker: "NVDA", asset_type: "equity", currency: "USD", exchange: "NASDAQ" },
	{ ticker: "GOOGL", asset_type: "equity", currency: "USD", exchange: "NASDAQ" },
	{ ticker: "VOO", asset_type: "etf", currency: "USD", exchange: "NYSEARCA" },
	{ ticker: "BND", asset_type: "etf", currency: "USD", exchange: "NASDAQ" },
] as const;
