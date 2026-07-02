"use client";

import * as React from "react";
import {
	BookOpen,
	Bot,
	Frame,
	Map,
	PieChart,
	Settings2,
	SquareTerminal,
} from "lucide-react";

import { NavMain } from "@/components/nav-main";
import { NavProjects } from "@/components/nav-projects";
import { NavUser } from "@/components/nav-user";
import { TeamSwitcher } from "@/components/team-switcher";
import {
	Sidebar,
	SidebarContent,
	SidebarFooter,
	SidebarHeader,
	SidebarRail,
} from "@/components/ui/sidebar";
import { useAuth } from "@/components/auth/auth-provider";
const data = {
	navMain: [
		{
			title: "Analytics",
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
			name: "Dashboard",
			url: "/dashboard",
			icon: SquareTerminal,
		},
		{
			name: "Chat Bot",
			url: "/chatbot",
			icon: Bot,
		},
		{
			name: "AI Analytics",
			url: "/ai-analytics",
			icon: PieChart,
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
			className="bg-white border-r border-gray-200"
		>
			<SidebarHeader className="bg-white border-b border-gray-200">
				<div className="flex items-center gap-2 px-2 py-2">
					<img
						src="/lumen.svg"
						alt="Lumen"
						className="w-8 h-8"
					/>
					<span className="text-xl font-bold text-gray-800 group-data-[collapsible=icon]:hidden">
						Lumen
					</span>
				</div>
			</SidebarHeader>
			<SidebarContent className="bg-white">
				<NavProjects projects={data.projects} />
				<NavMain items={data.navMain} />
			</SidebarContent>
			<SidebarFooter className="bg-white border-t border-gray-200">
				<NavUser user={user} />
			</SidebarFooter>
			<SidebarRail />
		</Sidebar>
	);
}
