"use client";

import { useState } from "react";
import { ExternalLink } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
	Sheet,
	SheetContent,
	SheetDescription,
	SheetHeader,
	SheetTitle,
} from "@/components/ui/sheet";
import type { Citation } from "@/lib/api/impact";

/**
 * Row of citation chips. Clicking a chip opens the side sheet with the full
 * quote and a link out to the source URL — the goal is to keep the reader on
 * the impact card while still giving them a one-click path to verify.
 */
export function CitationList({ citations }: { citations: Citation[] }) {
	const [active, setActive] = useState<Citation | null>(null);

	if (citations.length === 0) {
		return (
			<p className="text-sm text-muted-foreground">
				No citations were attached to this assessment.
			</p>
		);
	}

	return (
		<>
			<div className="flex flex-wrap gap-1.5">
				{citations.map((c, i) => (
					<button
						// citations can repeat source labels; use index for a stable key.
						key={`${c.url}-${i}`}
						type="button"
						onClick={() => setActive(c)}
						className="group inline-flex items-center gap-1.5 rounded-full border border-border bg-secondary/40 px-2.5 py-1 text-xs text-muted-foreground hover:border-primary/60 hover:bg-secondary hover:text-foreground focus-visible:outline-hidden focus-visible:ring-2 focus-visible:ring-ring"
					>
						<Badge variant="outline" className="border-0 p-0 text-[10px] uppercase text-muted-foreground group-hover:text-foreground">
							{c.source}
						</Badge>
						<span className="max-w-[220px] truncate">{c.title || c.url}</span>
					</button>
				))}
			</div>

			<Sheet open={active !== null} onOpenChange={(open) => !open && setActive(null)}>
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
										rel="noopener noreferrer"
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
