"use client";

/**
 * `useSse` — thin React wrapper around `openBackendStream` from
 * `@/lib/api/client`.
 *
 * We can't use the browser's native `EventSource` because the backend requires
 * Bearer auth on `/api/briefings/stream` and `EventSource` cannot send custom
 * headers. The shared `openBackendStream` drives SSE via `fetch()` + a
 * ReadableStream reader and yields typed `SseEvent` frames. This hook wraps
 * that generator in React state and lifecycle.
 *
 * Manual-start: the hook does not connect on mount. Callers invoke `start()`
 * to open the stream (typically from a button click). This matches the
 * briefing page's "Generate live" UX. `stop()` aborts via `AbortController`;
 * unmount also aborts.
 *
 * Terminal semantics: if a caller-supplied `parse` returns an event with
 * `event === "complete"` or `event === "error"`, the hook flips `done: true`
 * and stops the stream on its own. Non-terminal events accumulate in `events`
 * (append-only log) and `latest` (last frame).
 */

import { useCallback, useEffect, useRef, useState } from "react";

import { openBackendStream, type SseEvent } from "@/lib/api/client";

export type ParsedSseEvent<D = unknown> = {
	event: string;
	data: D;
};

export type UseSseOptions<T> = {
	path: string;
	method?: "GET" | "POST";
	body?: unknown;
	/** If `false` (default) the stream is manual; call `start()` to open it. */
	enabled?: boolean;
	/**
	 * Called for every parsed frame BEFORE state updates. Useful for imperative
	 * side effects — e.g. dispatching parsed payloads into another store.
	 */
	onEvent?: (evt: T) => void;
	/**
	 * Parse a raw `SseEvent` into the caller's typed frame. Return `null` to
	 * drop the frame. Defaults to JSON-parsing the `data` payload.
	 */
	parse?: (raw: SseEvent) => T | null;
};

export type UseSseState<T> = {
	connected: boolean;
	events: T[];
	latest: T | null;
	error: string | null;
	done: boolean;
};

export type UseSseReturn<T> = UseSseState<T> & {
	start: () => void;
	stop: () => void;
};

function defaultParse<T>(raw: SseEvent): T {
	// Best-effort JSON parse; if the payload isn't JSON, hand back the string.
	let data: unknown = raw.data;
	try {
		data = JSON.parse(raw.data);
	} catch {
		// leave as string
	}
	return { event: raw.event, data } as T;
}

function isTerminal<T>(evt: T): boolean {
	if (!evt || typeof evt !== "object") return false;
	const e = (evt as { event?: unknown }).event;
	return e === "complete" || e === "error";
}

export function useSse<T = ParsedSseEvent>(
	opts: UseSseOptions<T>,
): UseSseReturn<T> {
	const { path, method = "GET", body, enabled = false, onEvent, parse } = opts;

	const [connected, setConnected] = useState(false);
	const [events, setEvents] = useState<T[]>([]);
	const [latest, setLatest] = useState<T | null>(null);
	const [error, setError] = useState<string | null>(null);
	const [done, setDone] = useState(false);

	const abortRef = useRef<AbortController | null>(null);
	// Keep the latest callbacks accessible inside the running generator loop
	// without re-triggering `start`.
	const onEventRef = useRef<typeof onEvent>(onEvent);
	const parseRef = useRef<typeof parse>(parse);
	useEffect(() => {
		onEventRef.current = onEvent;
	}, [onEvent]);
	useEffect(() => {
		parseRef.current = parse;
	}, [parse]);

	const stop = useCallback(() => {
		abortRef.current?.abort();
		abortRef.current = null;
		setConnected(false);
	}, []);

	const start = useCallback(() => {
		// If a previous stream is still open, close it first.
		if (abortRef.current) {
			abortRef.current.abort();
		}
		const controller = new AbortController();
		abortRef.current = controller;
		setEvents([]);
		setLatest(null);
		setError(null);
		setDone(false);
		setConnected(true);

		const parser = parseRef.current ?? (defaultParse as (r: SseEvent) => T);

		(async () => {
			try {
				const stream = openBackendStream(path, {
					method,
					body: body === undefined ? undefined : JSON.stringify(body),
					signal: controller.signal,
				});
				for await (const raw of stream) {
					if (controller.signal.aborted) break;
					const evt = parser(raw);
					if (evt === null || evt === undefined) continue;
					onEventRef.current?.(evt);
					setLatest(evt);
					setEvents((prev) => [...prev, evt]);
					if (isTerminal(evt)) {
						setDone(true);
						break;
					}
				}
			} catch (err) {
				if (controller.signal.aborted) return;
				const message = err instanceof Error ? err.message : String(err);
				setError(message);
				setDone(true);
			} finally {
				if (abortRef.current === controller) {
					abortRef.current = null;
				}
				setConnected(false);
			}
		})();
	}, [path, method, body]);

	// Auto-start when `enabled` flips true. `enabled` defaults to false so most
	// callers use manual `start()`.
	useEffect(() => {
		if (enabled) start();
		// Cleanup on unmount / re-run: abort any in-flight stream.
		return () => {
			abortRef.current?.abort();
			abortRef.current = null;
		};
	}, [enabled, start]);

	return { connected, events, latest, error, done, start, stop };
}
