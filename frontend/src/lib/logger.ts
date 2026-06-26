/**
 * Frontend logger.
 *
 * Use `logger.debug` / `logger.info` for development noise — they are no-ops
 * in production builds. Use `logger.warn` / `logger.error` for genuine
 * problems; those always emit (kept routed to `console` so they show up in
 * the browser devtools and in any error tracker that hooks console.error).
 *
 * Why this exists: the codebase had ~65 stray console.log calls (emoji-tagged
 * progress traces, "[v0]" landing-page diagnostics, stub button handlers).
 * They leaked debug output into production and made real warnings hard to see.
 */

const isProd = process.env.NODE_ENV === "production";

type LogArgs = Parameters<typeof console.log>;

const noop = (..._args: LogArgs): void => {};

export const logger = {
	debug: isProd ? noop : (...args: LogArgs) => console.log(...args),
	info: isProd ? noop : (...args: LogArgs) => console.info(...args),
	warn: (...args: LogArgs) => console.warn(...args),
	error: (...args: LogArgs) => console.error(...args),
};
