import type { Metadata } from "next";
import { GlassmorphismNav } from "@/components/landing/glassmorphism-nav";
import { HeroSection } from "@/components/landing/hero-section";
import { ProblemSolutionSection } from "@/components/landing/problem-solution-section";
import Aurora from "@/components/landing/Aurora";
import { FeaturesSection } from "@/components/landing/features-section";
import { AITeamSection } from "@/components/landing/ai-team-section";
import { TestimonialsSection } from "@/components/landing/testimonials-section";
import { ROICalculatorSection } from "@/components/landing/roi-calculator-section";
import { CTASection } from "@/components/landing/cta-section";
import { Footer } from "@/components/landing/footer";

export const metadata: Metadata = {
	title: "AI Financial Dashboard for Invoice Operations",
	description:
		"Capture invoices, analyze spend, detect anomalies, and ask finance questions faster with Lumen's AI-powered financial dashboard.",
	alternates: {
		canonical: "/",
	},
	openGraph: {
		url: "/",
		title: "AI Financial Dashboard for Invoice Operations | Lumen",
		description:
			"Capture invoices, analyze spend, detect anomalies, and ask finance questions faster with Lumen's AI-powered financial dashboard.",
	},
	twitter: {
		title: "AI Financial Dashboard for Invoice Operations | Lumen",
		description:
			"Capture invoices, analyze spend, detect anomalies, and ask finance questions faster with Lumen's AI-powered financial dashboard.",
	},
};

export default function HomePage() {
	return (
		<div className="min-h-screen bg-black overflow-hidden">
			<main className="min-h-screen relative overflow-hidden">
				<div className="fixed inset-0 w-full h-full">
					<Aurora
						colorStops={["#475569", "#64748b", "#475569"]}
						amplitude={1.2}
						blend={0.6}
						speed={0.8}
					/>
				</div>
				<div className="relative z-10">
					<GlassmorphismNav />
					<HeroSection />
					<ProblemSolutionSection />
					<FeaturesSection />
					<AITeamSection />
					<TestimonialsSection />
					<ROICalculatorSection />
					<CTASection />
					<Footer />
				</div>
			</main>
		</div>
	);
}
