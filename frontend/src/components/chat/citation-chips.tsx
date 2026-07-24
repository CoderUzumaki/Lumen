"use client";

/**
 * Numbered citation chips rendered directly beneath an assistant bubble.
 *
 * Chip → click opens a right-side Sheet with the citation's source / title /
 * full quote and an "Open source" button (external link). Same UX shape as
 * `components/impact/citation-panel.tsx` but tuned for the chat layout —
 * chips are numbered `[1]`, `[2]`… so the assistant text can reference them
 * implicitly.
 *
 * The hover-tooltip shows source + title without opening the sheet — useful
 * for a quick scan.
 */

import { useState } from "react";
import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "@/components/ui/tooltip";
import type { Citation } from "@/lib/api/impact";

export function CitationChips({ citations }: { citations: Citation[] }) {
	const [active, setActive] = useState<Citation | null>(null);

	if (!citations || citations.length === 0) {
		return null;
	}

	return (
		<>
			<TooltipProvider delayDuration={150}>
				<div className="mt-2 flex flex-wrap gap-1.5">
					{citations.map((c, i) => (
						<Tooltip key={`${c.url}-${i}`}>
							<TooltipTrigger asChild>
								<button
									type="button"
									onClick={() => setActive(c)}
									className="inline-flex items-center rounded-full border border-border bg-secondary/40 px-2 py-0.5 text-[11px] font-mono text-muted-foreground transition-colors hover:border-primary/60 hover:bg-secondary hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
									aria-label={`Citation ${i + 1}: ${c.source}${c.title ? ` — ${c.title}` : ""}`}
								>
									[{i + 1}]
								</button>
							</TooltipTrigger>
							<TooltipContent side="top" className="max-w-xs">
								<p className="font-mono text-[10px] uppercase text-muted">
									{c.source}
								</p>
								{c.title ? (
									<p className="mt-0.5 text-xs">{c.title}</p>
								) : (
									<p className="mt-0.5 text-xs italic opacity-80">
										{c.url}
									</p>
								)}
							</TooltipContent>
						</Tooltip>
					))}
				</div>
			</TooltipProvider>

			<Sheet
				open={active !== null}
				onOpenChange={(open) => !open && setActive(null)}
			>
				<SheetContent side="right" className="w-full sm:max-w-md">
					<SheetHeader>
						<SheetTitle className="pr-8 leading-snug">
							{active?.title ?? "Citation"}
						</SheetTitle>
						<SheetDescription>
							From{" "}
							<span className="font-mono uppercase">{active?.source}</span>
						</SheetDescription>
					</SheetHeader>

					{active ? (
						<div className="flex-1 overflow-y-auto px-4 pb-4">
							<blockquote className="border-l-2 border-primary/60 pl-3 text-sm leading-relaxed text-foreground">
								{active.quote}
							</blockquote>
							<div className="mt-4">
								<Button asChild variant="outline" size="sm">
									<a
										href={active.url}
										target="_blank"
										rel="noreferrer"
									>
										<ExternalLink className="mr-2 h-3.5 w-3.5" />
										Open source
									</a>
								</Button>
							</div>
						</div>
					) : null}
				</SheetContent>
			</Sheet>
		</>
	);
}
