"use client";

/**
 * Shared fetch client for the FastAPI backend.
 *
 * Every module that hits `/api/...` — portfolios, news, impact, briefings —
 * routes through `apiFetch` (or, for SSE, `openBackendStream`) so auth-header
 * attachment and envelope-error extraction stay in one place.
 *
 * Auth: pulls the current Supabase session's `access_token` from the browser
 * client and attaches it as `Bearer`. The backend (`app.utils.auth.require_auth`)
 * verifies it against the Supabase JWKS endpoint. Callers must be inside an
 * `<AuthGuard>` boundary — no session → throws.
 */

import { getSupabaseBrowserClient } from "@/lib/supabase/client";

export const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL;

if (!BACKEND_URL) {
	console.warn(
		"NEXT_PUBLIC_BACKEND_URL is not set; backend API calls will fail.",
	);
}

export async function currentAccessToken(): Promise<string> {
	const supabase = getSupabaseBrowserClient();
	const { data } = await supabase.auth.getSession();
	const token = data.session?.access_token;
	if (!token) {
		throw new Error("Not signed in — no Supabase session.");
	}
	return token;
}

export type ApiFetchOptions = RequestInit & { parseJson?: boolean };

/**
 * Fetch a backend JSON endpoint. Attaches the Supabase access token and
 * extracts a useful `detail` on non-2xx (envelope-aware: `body.error.message`
 * or `body.detail`).
 *
 * `parseJson: false` skips response.json() — use for DELETE/204 responses.
 * A 202 body (impact / briefing enqueue) is returned verbatim so the caller
 * can distinguish `{status: "generating", poll_url}` from the success shape.
 */
export async function apiFetch<T>(
	path: string,
	init: ApiFetchOptions = {},
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
		return undefined as T;
	}
	return (await res.json()) as T;
}

/**
 * Fetch that never throws on non-2xx — returns the raw Response instead.
 * Used by callers that need to branch on status (e.g. impact endpoint's 200
 * vs 202 vs 404 flow).
 */
export async function apiFetchRaw(
	path: string,
	init: RequestInit = {},
): Promise<Response> {
	const token = await currentAccessToken();
	return fetch(`${BACKEND_URL}${path}`, {
		...init,
		headers: {
			"Content-Type": "application/json",
			Authorization: `Bearer ${token}`,
			...(init.headers ?? {}),
		},
	});
}

/**
 * One frame of a text/event-stream response — an SSE event.
 * `event` defaults to "message" per the spec.
 */
export type SseEvent = { event: string; data: string };

/**
 * Open a backend SSE stream with Bearer auth.
 *
 * EventSource can't set custom headers, so we drive the stream via fetch()
 * + a ReadableStream reader and parse SSE frames ourselves. Yields one
 * `SseEvent` per complete frame (a run of non-empty lines terminated by a
 * blank line). Multiline `data:` lines are joined with `\n` per the spec.
 *
 * The `signal` option lets callers abort (e.g. React unmount / manual "stop
 * stream" button). On any read error, iteration ends cleanly.
 */
export async function* openBackendStream(
	path: string,
	init: { method?: "GET" | "POST"; body?: string; signal?: AbortSignal } = {},
): AsyncGenerator<SseEvent, void, void> {
	const token = await currentAccessToken();
	const res = await fetch(`${BACKEND_URL}${path}`, {
		method: init.method ?? "GET",
		body: init.body,
		signal: init.signal,
		headers: {
			Accept: "text/event-stream",
			Authorization: `Bearer ${token}`,
			...(init.body ? { "Content-Type": "application/json" } : {}),
		},
	});
	if (!res.ok || !res.body) {
		let detail: string | undefined;
		try {
			const body = await res.json();
			detail = body?.error?.message ?? body?.detail;
		} catch {
			// leave undefined
		}
		throw new Error(
			`SSE ${init.method ?? "GET"} ${path} → ${res.status}${
				detail ? `: ${detail}` : ""
			}`,
		);
	}

	const reader = res.body.getReader();
	const decoder = new TextDecoder();
	let buffer = "";

	try {
		while (true) {
			const { done, value } = await reader.read();
			if (done) break;
			buffer += decoder.decode(value, { stream: true });

			let sep: number;
			// SSE frames are separated by a blank line ("\n\n"). Some servers
			// use "\r\n\r\n"; handle both by normalizing.
			buffer = buffer.replace(/\r\n/g, "\n");
			while ((sep = buffer.indexOf("\n\n")) !== -1) {
				const raw = buffer.slice(0, sep);
				buffer = buffer.slice(sep + 2);
				const frame = parseFrame(raw);
				if (frame) yield frame;
			}
		}
	} finally {
		try {
			reader.releaseLock();
		} catch {
			// already released
		}
	}
}

function parseFrame(raw: string): SseEvent | null {
	let event = "message";
	const dataLines: string[] = [];
	for (const line of raw.split("\n")) {
		if (!line || line.startsWith(":")) continue;
		const colon = line.indexOf(":");
		const field = colon === -1 ? line : line.slice(0, colon);
		const value =
			colon === -1
				? ""
				: line.slice(colon + 1).startsWith(" ")
					? line.slice(colon + 2)
					: line.slice(colon + 1);
		if (field === "event") event = value;
		else if (field === "data") dataLines.push(value);
		// id / retry fields ignored — we don't need reconnect semantics here.
	}
	if (dataLines.length === 0) return null;
	return { event, data: dataLines.join("\n") };
}
