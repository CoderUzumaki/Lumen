"use client";

/**
 * Render one `ScenarioSimulation` — the full result of one scenario × one
 * portfolio.
 *
 * Reading order:
 *   1. Portfolio summary (prose block, multi-line)
 *   2. Per-position impact cards
 *   3. Key assumptions (bulleted)
 *   4. Falsifiability callout ("what would flip this read")
 *   5. Historical analogs
 *   6. Citations (chips, or the "hypothetical scenario" note when empty)
 *
 * Deviation from PRD principle #1: scenarios can have empty `citations`
 * because a hypothetical scenario has no concrete news sources — the graph
 * leans on historical analogs for grounding. We surface that explicitly rather
 * than showing an empty section.
 */

import { AlertTriangle, TrendingUp } from "lucide-react";

import { AnalogCard } from "@/components/impact/analog-card";
import { CitationList } from "@/components/impact/citation-panel";
import { PositionImpactCard } from "@/components/scenarios/position-impact-card";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import type { ScenarioSimulation } from "@/lib/api/scenarios";

export function SimulationView({
	simulation,
}: {
	simulation: ScenarioSimulation;
}) {
	return (
		<div className="space-y-8">
			<Card>
				<CardHeader>
					<CardTitle className="text-base font-medium tracking-tight text-muted-foreground">
						Scenario
					</CardTitle>
					<CardDescription className="text-sm leading-relaxed text-foreground">
						{simulation.scenario_text}
					</CardDescription>
				</CardHeader>
			</Card>

			<section>
				<p className="mb-2 text-xs uppercase tracking-widest text-muted-foreground">
					Portfolio summary
				</p>
				<div className="whitespace-pre-line rounded-lg border border-border bg-card/50 p-4 text-sm leading-relaxed text-foreground">
					{simulation.portfolio_summary}
				</div>
			</section>

			<Separator />

			<section>
				<div className="mb-4 flex items-center gap-2 text-xs uppercase tracking-widest text-muted-foreground">
					<TrendingUp className="h-4 w-4" />
					<span>Per-position impact</span>
				</div>
				{simulation.per_position_impact.length === 0 ? (
					<p className="text-sm text-muted-foreground">
						No position-level impact identified.
					</p>
				) : (
					<div className="grid gap-4 sm:grid-cols-2">
						{simulation.per_position_impact.map((impact) => (
							<PositionImpactCard key={impact.ticker} impact={impact} />
						))}
					</div>
				)}
			</section>

			{simulation.key_assumptions.length > 0 ? (
				<>
					<Separator />
					<section>
						<p className="mb-3 text-xs uppercase tracking-widest text-muted-foreground">
							Key assumptions
						</p>
						<Card>
							<CardContent className="pt-6">
								<ul className="space-y-3">
									{simulation.key_assumptions.map((assumption, i) => (
										<li
											key={`${i}-${assumption.slice(0, 24)}`}
											className="flex gap-3 text-sm leading-relaxed"
										>
											<span
												className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-primary"
												aria-hidden
											/>
											<span>{assumption}</span>
										</li>
									))}
								</ul>
							</CardContent>
						</Card>
					</section>
				</>
			) : null}

			<Separator />

			<Alert>
				<AlertTriangle className="h-4 w-4" />
				<AlertTitle>Falsifiability</AlertTitle>
				<AlertDescription>{simulation.falsifiability}</AlertDescription>
			</Alert>

			{simulation.historical_analogs.length > 0 ? (
				<>
					<Separator />
					<section>
						<p className="mb-2 text-xs uppercase tracking-widest text-muted-foreground">
							Historical analogs
						</p>
						<div className="grid gap-2 sm:grid-cols-2">
							{simulation.historical_analogs.map((analog, i) => (
								<AnalogCard key={`${analog.when}-${i}`} analog={analog} />
							))}
						</div>
					</section>
				</>
			) : null}

			<Separator />

			<section>
				<p className="mb-2 text-xs uppercase tracking-widest text-muted-foreground">
					Citations
				</p>
				{simulation.citations.length === 0 ? (
					<p className="text-sm italic text-muted-foreground">
						This scenario is hypothetical — grounded in historical analogs
						rather than sourced claims.
					</p>
				) : (
					<CitationList citations={simulation.citations} />
				)}
			</section>
		</div>
	);
}
