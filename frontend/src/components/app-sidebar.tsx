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
import { authApi, tokenManager } from "@/lib/api/client"; // This is sample data.
const data = {
	navMain: [
		{
			title: "Analytics",
			url: "#",
			icon: BookOpen,
			items: [
				{
					title: "Weekly",
					url: "#",
				},
				{
					title: "Monthly",
					url: "#",
				},
				{
					title: "Yearly",
					url: "#",
				},
				{
					title: "Custom",
					url: "#",
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
	],
};

export function AppSidebar({ ...props }: React.ComponentProps<typeof Sidebar>) {
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
		const fetchUserData = async () => {
			if (typeof window !== "undefined") {
				// First try to get from localStorage
				const userStr = localStorage.getItem("invox_user");
				if (userStr) {
					const userData = JSON.parse(userStr);
					setUser({
						name: userData.name || "User",
						email: userData.email || "user@example.com",
						avatar:
							userData.picture ||
							`https://ui-avatars.com/api/?name=${encodeURIComponent(
								userData.name || "User"
							)}&background=random`,
					});
				} else {
					// If not in localStorage, fetch from backend
					try {
						const userData = await authApi.getCurrentUser();
						tokenManager.setUser(userData);
						setUser({
							name: userData.name || "User",
							email: userData.email || "user@example.com",
							avatar:
								userData.picture ||
								`https://ui-avatars.com/api/?name=${encodeURIComponent(
									userData.name || "User"
								)}&background=random`,
						});
					} catch (error) {
						console.error("Error fetching user data:", error);
					}
				}
			}
		};

		fetchUserData();
	}, []);

	return (
		<Sidebar collapsible="icon" {...props}>
			<SidebarHeader>
				<div className="flex items-center gap-2 px-2 py-2">
					<img
						src="/lumen.svg"
						alt="Invox Logo"
						className="w-8 h-8"
					/>
					<span className="text-xl font-bold text-gray-800 group-data-[collapsible=icon]:hidden">
						Lumen
					</span>
				</div>
			</SidebarHeader>
			<SidebarContent>
				<NavProjects projects={data.projects} />
				<NavMain items={data.navMain} />
			</SidebarContent>
			<SidebarFooter>
				<NavUser user={user} />
			</SidebarFooter>
			<SidebarRail />
		</Sidebar>
	);
}
