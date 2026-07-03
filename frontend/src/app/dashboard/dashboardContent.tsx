"use client";

import AnimatedListItemUse from "@/components/animatedListItemUse";
import { SectionCards } from "@/components/section-cards";
import { DashboardShell } from "@/components/dashboard-shell";
import { DialogDemo } from "@/components/uploadDialog";
import { ExportDialog } from "@/components/exportDialog";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { useSearchParams } from "next/navigation";

export default function DashboardContent() {
	const searchParams = useSearchParams();
	const openUpload = searchParams.get("upload") === "1";

	return (
		<DashboardShell
			title="Financial Overview"
			description="Track invoice intake, review queue health, and recent transaction activity from one workspace designed for fast decision-making."
			eyebrow="Operations"
			actions={
				<>
					<ExportDialog />
					<DialogDemo defaultOpen={openUpload} />
				</>
			}
		>
			<div className="grid auto-rows-fr gap-4 md:grid-cols-2 xl:grid-cols-4">
				<SectionCards />
			</div>

			<div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_320px]">
				<Card className="border-border/70 bg-card/80 shadow-lg shadow-black/10">
					<CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
						<div>
							<CardTitle className="text-xl">
								Invoice overview
							</CardTitle>
							<CardDescription>
								Review recent uploads, open vendor records, and
								move quickly from extraction to approval.
							</CardDescription>
						</div>
						<Badge
							variant="outline"
							className="w-fit rounded-full border-border/70 bg-background/60 px-3 py-1 text-xs text-muted-foreground"
						>
							Latest activity
						</Badge>
					</CardHeader>
					<CardContent>
						<AnimatedListItemUse />
					</CardContent>
				</Card>

				<Card className="border-border/70 bg-card/80 shadow-lg shadow-black/10">
					<CardHeader>
						<CardTitle className="text-xl">
							What to watch
						</CardTitle>
						<CardDescription>
							The fastest path to the answers finance teams need
							most often.
						</CardDescription>
					</CardHeader>
					<CardContent className="space-y-4 text-sm text-muted-foreground">
						<div className="rounded-2xl border border-border/70 bg-background/60 p-4">
							<p className="font-medium text-foreground">
								Approval queue
							</p>
							<p className="mt-1 leading-6">
								Prioritize records with missing fields, unusual
								spend, or OCR confidence issues before payment
								approval.
							</p>
						</div>
						<div className="rounded-2xl border border-border/70 bg-background/60 p-4">
							<p className="font-medium text-foreground">
								Exports and reporting
							</p>
							<p className="mt-1 leading-6">
								Package the current ledger view for downstream
								reporting without leaving the dashboard.
							</p>
						</div>
						<div className="rounded-2xl border border-border/70 bg-background/60 p-4">
							<p className="font-medium text-foreground">
								Recent imports
							</p>
							<p className="mt-1 leading-6">
								Use the upload action whenever a new batch needs
								review or email polling is paused.
							</p>
						</div>
					</CardContent>
				</Card>
			</div>
		</DashboardShell>
	);
}
