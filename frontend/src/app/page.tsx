import Link from "next/link";

// Placeholder landing. DEPLOY-05 replaces this with the real marketing page
// (hero + 20-second briefing demo GIF + product principles). The current
// content is intentionally minimal so BOOT-04's `/` acceptance passes without
// pulling in any design work.

export default function LandingPage() {
	return (
		<main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start justify-center gap-8 px-6 py-16">
			<div className="space-y-3">
				<p className="text-sm uppercase tracking-widest text-muted-foreground">
					Lumen
				</p>
				<h1 className="text-4xl font-semibold tracking-tight">
					Personal Financial Intelligence Agent
				</h1>
				<p className="max-w-2xl text-lg text-muted-foreground">
					Give it your portfolio and the macro themes you care about. It watches
					the world&apos;s financial news continuously, reasons about which of it
					materially affects your holdings, and produces a personalized daily
					briefing plus an ask-anything chat — with citations, no buy/sell
					recommendations, and a public track record of its own predictions.
				</p>
			</div>

			<div className="flex flex-wrap items-center gap-3">
				<Link
					href="/signin"
					className="inline-flex items-center rounded-md border border-border bg-primary px-4 py-2 text-sm font-medium text-primary-foreground transition-colors hover:opacity-90"
				>
					Sign in
				</Link>
				<a
					href="https://github.com/CoderUzumaki/Lumen"
					className="inline-flex items-center rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground transition-colors hover:bg-secondary"
					target="_blank"
					rel="noreferrer"
				>
					View source
				</a>
			</div>

			<p className="text-xs text-muted-foreground">
				Lumen provides analysis, not advice. No buy / sell / hold recommendations.
			</p>
		</main>
	);
}
