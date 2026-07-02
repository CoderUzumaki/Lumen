import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "@/components/providers";

export const metadata: Metadata = {
	title: "Lumen — Personal Financial Intelligence Agent",
	description:
		"Personalized financial intelligence: watches the world's financial news continuously, reasons about which of it materially affects your holdings, and produces cited daily briefings.",
	icons: {
		icon: "/favicon.ico",
	},
};

export default function RootLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<html lang="en" className="dark" data-theme="dark">
			<body>
				<Providers>{children}</Providers>
			</body>
		</html>
	);
}
