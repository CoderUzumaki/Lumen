import React, { Dispatch, SetStateAction } from "react";
import { Sun, Moon } from "lucide-react";

interface ThemeToggleProps {
	theme: string;
	setTheme: Dispatch<SetStateAction<string>>;
}

export default function ThemeToggle({ theme, setTheme }: ThemeToggleProps) {
	return (
		<button
			className="inline-flex items-center gap-2 rounded-full border border-zinc-200 bg-white px-2.5 py-1.5 text-sm hover:bg-zinc-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-blue-500 dark:border-zinc-800 dark:bg-zinc-950 dark:hover:bg-zinc-800"
			onClick={() => setTheme((t) => (t === "dark" ? "light" : "dark"))}
			aria-label="Toggle theme"
			title="Toggle theme"
		>
			{theme === "dark" ? (
				<Sun className="h-4 w-4" />
			) : (
				<Moon className="h-4 w-4" />
			)}
			<span className="hidden sm:inline">
				{theme === "dark" ? "Light" : "Dark"}
			</span>
		</button>
	);
}
