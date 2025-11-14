"use client";
import { Asterisk, MoreHorizontal, Menu, ChevronDown } from "lucide-react";
import { useState, ReactNode } from "react";

interface Chatbot {
	name: string;
	icon: string | ReactNode;
}

interface HeaderProps {
	createNewChat: () => void;
	sidebarCollapsed: boolean;
	setSidebarOpen: (open: boolean) => void;
}

export default function Header({
	createNewChat,
	sidebarCollapsed,
	setSidebarOpen,
}: HeaderProps) {
	const [selectedBot, setSelectedBot] = useState("GPT-5");
	const [isDropdownOpen, setIsDropdownOpen] = useState(false);

	const chatbots: Chatbot[] = [
		{ name: "GPT-5", icon: "🤖" },
		{ name: "Claude Sonnet 4", icon: "🎭" },
		{ name: "Gemini", icon: "💎" },
		{ name: "Assistant", icon: <Asterisk className="h-4 w-4" /> },
	];

	return (
		<div className="sticky top-0 z-30 flex items-center gap-2 border-b border-zinc-200/60 bg-white/80 px-4 py-3 backdrop-blur dark:border-zinc-800 dark:bg-zinc-900/70">
			{sidebarCollapsed && (
				<button
					onClick={() => setSidebarOpen(true)}
					className="md:hidden inline-flex items-center justify-center rounded-lg p-2 hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:hover:bg-zinc-800"
					aria-label="Open sidebar"
				>
					<Menu className="h-5 w-5" />
				</button>
			)}
		</div>
	);
}
