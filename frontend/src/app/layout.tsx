import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { AuthProvider } from "@/components/auth/auth-provider";

const siteUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
const metadataBase = new URL(siteUrl);

const inter = Inter({
	subsets: ["latin"],
	variable: "--font-sans",
});

const jetBrainsMono = JetBrains_Mono({
	subsets: ["latin"],
	variable: "--font-mono",
});

export const metadata: Metadata = {
	metadataBase,
	applicationName: "Lumen",
	title: {
		default: "Lumen | AI Financial Dashboard for Invoice Operations",
		template: "%s | Lumen",
	},
	description:
		"Lumen is an AI financial dashboard for invoice operations, spend visibility, anomaly detection, and faster finance workflows.",
	keywords: [
		"financial dashboard",
		"invoice management",
		"accounts payable",
		"spend analytics",
		"invoice OCR",
		"finance automation",
		"anomaly detection",
	],
	category: "finance",
	creator: "Lumen",
	publisher: "Lumen",
	referrer: "origin-when-cross-origin",
	formatDetection: {
		email: false,
		address: false,
		telephone: false,
	},
	robots: {
		index: true,
		follow: true,
		googleBot: {
			index: true,
			follow: true,
			maxSnippet: -1,
			maxImagePreview: "large",
			maxVideoPreview: -1,
		},
	},
	openGraph: {
		type: "website",
		locale: "en_US",
		siteName: "Lumen",
		title: "Lumen | AI Financial Dashboard for Invoice Operations",
		description:
			"Lumen helps finance teams capture invoices, monitor spend, detect anomalies, and move faster through review and close.",
		images: [
			{
				url: "/favicon_io/android-chrome-512x512.png",
				width: 512,
				height: 512,
				alt: "Lumen logo",
			},
		],
	},
	twitter: {
		card: "summary_large_image",
		title: "Lumen | AI Financial Dashboard for Invoice Operations",
		description:
			"AI-powered invoice operations, spend visibility, anomaly detection, and finance workflow acceleration.",
		images: ["/favicon_io/android-chrome-512x512.png"],
	},
	manifest: "/favicon_io/site.webmanifest",
	icons: {
		icon: [
			{ url: "/favicon_io/favicon.ico" },
			{
				url: "/favicon_io/favicon-16x16.png",
				sizes: "16x16",
				type: "image/png",
			},
			{
				url: "/favicon_io/favicon-32x32.png",
				sizes: "32x32",
				type: "image/png",
			},
		],
		shortcut: "/favicon_io/favicon.ico",
		apple: [
			{
				url: "/favicon_io/apple-touch-icon.png",
				sizes: "180x180",
				type: "image/png",
			},
		],
	},
};

export default function RootLayout({
	children,
}: {
	children: React.ReactNode;
}) {
	return (
		<html
			lang="en"
			className={`${inter.variable} ${jetBrainsMono.variable} dark`}
		>
			<body className="min-h-screen bg-background font-sans text-foreground antialiased">
				<AuthProvider>{children}</AuthProvider>
			</body>
		</html>
	);
}
