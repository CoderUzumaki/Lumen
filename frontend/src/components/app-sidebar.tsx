"use client";

import * as React from "react";
import {
	BookOpen,
	Bot,
	PieChart,
	LayoutDashboard,
} from "lucide-react";
import Image from "next/image";

import { NavMain } from "@/components/nav-main";
import { NavProjects } from "@/components/nav-projects";
import { NavUser } from "@/components/nav-user";
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarGroupLabel,
	SidebarHeader,
	SidebarRail,
} from "@/components/ui/sidebar";
import { useAuth } from "@/components/auth/auth-provider";

const data = {
	navMain: [
		{
			title: "Spending Views",
			url: "#",
			icon: BookOpen,
			items: [
				{
					title: "Weekly",
					url: "/analytics?tab=weekly",
				},
				{
					title: "Monthly",
					url: "/analytics?tab=monthly",
				},
				{
					title: "Yearly",
					url: "/analytics?tab=yearly",
				},
			],
		},
	],
	projects: [
		{
			name: "Overview",
			url: "/dashboard",
			icon: LayoutDashboard,
		},
		{
			name: "Analytics",
			url: "/analytics",
			icon: BookOpen,
		},
		{
			name: "AI Insights",
			url: "/ai-analytics",
			icon: PieChart,
		},
		{
			name: "Ask Lumen",
			url: "/chatbot",
			icon: Bot,
		},
	],
};

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
	const { user: authUser } = useAuth();
	const [user, setUser] = React.useState<{
		name: string;
		email: string;
		avatar: string;
	}>({
		name: "User",
		email: "user@example.com",
		avatar: "https://ui-avatars.com/api/?name=User&background=random",
	});

	React.useEffect(() => {
		if (!authUser) {
			return;
		}

		const name =
			authUser.user_metadata?.full_name ??
			authUser.user_metadata?.name ??
			authUser.email ??
			"User";
		const avatar =
			authUser.user_metadata?.avatar_url ??
			authUser.user_metadata?.picture ??
			`https://ui-avatars.com/api/?name=${encodeURIComponent(
				name
			)}&background=random`;

		setUser({
			name,
			email: authUser.email || "user@example.com",
			avatar,
		});
	}, [authUser]);

	return (
		<Sidebar
			collapsible="icon"
			{...props}
			className="border-r border-sidebar-border/80"
		>
			<SidebarHeader className="border-b border-sidebar-border/80 px-3 py-3">
				<div className="flex items-center gap-3">
					<Image
						src="/lumen_logo.svg"
						alt="Lumen logo"
						width={32}
						height={32}
						className="h-8 w-8"
					/>
					<div className="group-data-[collapsible=icon]:hidden">
						<p className="text-sm font-semibold tracking-wide text-sidebar-foreground">
							Lumen
						</p>
						<p className="text-xs text-sidebar-foreground/60">
							Financial command center
						</p>
					</div>
				</div>
			</SidebarHeader>
			<SidebarContent className="px-1 py-3">
				<SidebarGroupLabel>Workspace</SidebarGroupLabel>
				<NavProjects projects={data.projects} />
				<SidebarGroupLabel className="mt-2">Compare</SidebarGroupLabel>
				<NavMain items={data.navMain} />
			</SidebarContent>
			<SidebarFooter className="border-t border-sidebar-border/80 pt-3">
				<NavUser user={user} />
			</SidebarFooter>
			<SidebarRail />
		</Sidebar>
	);
}
