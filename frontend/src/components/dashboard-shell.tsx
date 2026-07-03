"use client";

import type { ReactNode } from "react";
import { AppSidebar } from "@/components/app-sidebar";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
	SidebarInset,
	SidebarProvider,
	SidebarTrigger,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

interface DashboardShellProps {
	title: string;
	description: string;
	children: ReactNode;
	actions?: ReactNode;
	toolbar?: ReactNode;
	eyebrow?: string;
	contentClassName?: string;
}

export function DashboardShell({
	title,
	description,
	children,
	actions,
	toolbar,
	eyebrow = "Finance Workspace",
	contentClassName,
}: DashboardShellProps) {
	return (
		<SidebarProvider>
			<AppSidebar />
			<SidebarInset className="min-h-screen bg-transparent">
				<header className="sticky top-0 z-20 border-b border-border/70 bg-background/80 backdrop-blur-xl">
					<div className="flex h-14 items-center gap-3 px-4 sm:px-6 lg:px-8">
						<SidebarTrigger className="-ml-1 text-muted-foreground hover:text-foreground" />
						<Separator orientation="vertical" className="h-4" />
						<div className="text-sm font-medium text-muted-foreground">
							Lumen
						</div>
					</div>
				</header>
				<div
					className={cn(
						"flex flex-1 flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8",
						contentClassName
					)}
				>
					<section className="rounded-3xl border border-border/70 bg-card/70 px-5 py-5 shadow-sm shadow-black/10 sm:px-6">
						<div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
							<div className="space-y-3">
								<Badge
									variant="outline"
									className="w-fit rounded-full border-primary/25 bg-primary/10 px-3 py-1 text-[11px] font-semibold tracking-[0.16em] uppercase text-primary"
								>
									{eyebrow}
								</Badge>
								<div className="space-y-2">
									<h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">
										{title}
									</h1>
									<p className="max-w-3xl text-sm leading-6 text-muted-foreground sm:text-base">
										{description}
									</p>
								</div>
							</div>
							{actions && (
								<div className="flex flex-wrap items-center gap-3">
									{actions}
								</div>
							)}
						</div>
						{toolbar && (
							<div className="mt-5 border-t border-border/70 pt-5">
								{toolbar}
							</div>
						)}
					</section>
					{children}
				</div>
			</SidebarInset>
		</SidebarProvider>
	);
}
