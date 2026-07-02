"use client";

import { useEffect, type ReactNode } from "react";

/**
 * Minimal ThemeProvider — Lumen ships dark-first per PRD §8 and BUILD.md's
 * design-system section. This component pins `data-theme="dark"` and the
 * shadcn `dark` class on `<html>`. A light-mode toggle is deferred to v0.2.
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
	useEffect(() => {
		const root = document.documentElement;
		root.setAttribute("data-theme", "dark");
		root.classList.add("dark");
		return () => {
			// intentionally no cleanup — the theme is a page-level attribute.
		};
	}, []);

	return <>{children}</>;
}
