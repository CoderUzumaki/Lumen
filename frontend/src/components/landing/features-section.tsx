"use client";

import { useEffect, useRef, useState } from "react";
import {
	Bot,
	CalendarRange,
	ChartColumn,
	ReceiptText,
	ShieldCheck,
	Sparkles,
} from "lucide-react";

const featureCards = [
	{
		title: "Capture and classify invoices automatically",
		description:
			"Extract vendor, amount, date, and category data in seconds so your team stops keying the same information by hand.",
		eyebrow: "Invoice Capture",
		metric: "95%+",
		metricLabel: "OCR accuracy on structured invoices",
		highlights: ["Line-item extraction", "Vendor normalization", "Review-ready fields"],
		icon: ReceiptText,
		span: "md:col-span-2",
	},
	{
		title: "Catch risk before payment leaves",
		description:
			"Highlight unusual amounts, duplicate charges, and missing context while the transaction is still in review.",
		eyebrow: "Risk Controls",
		metric: "3x",
		metricLabel: "faster exception triage",
		highlights: ["Duplicate detection", "Missing field alerts", "High-risk flags"],
		icon: ShieldCheck,
	},
	{
		title: "Track due dates and upcoming cash demand",
		description:
			"Keep a current picture of commitments, forecasted payments, and the items most likely to disrupt close.",
		eyebrow: "Calendar Intelligence",
		metric: "Live",
		metricLabel: "payment calendar and reminders",
		highlights: ["Upcoming obligations", "Forecasted outflow", "Reminder queue"],
		icon: CalendarRange,
	},
	{
		title: "See spend shifts across categories and periods",
		description:
			"Move from raw transactions to clear trend lines, vendor concentration, and category-level performance.",
		eyebrow: "Spend Visibility",
		metric: "Weekly to yearly",
		metricLabel: "comparisons in one dashboard",
		highlights: ["Period comparisons", "Vendor mix", "Category breakdowns"],
		icon: ChartColumn,
		span: "md:col-span-2",
	},
	{
		title: "Ask finance questions in plain language",
		description:
			"Use the Lumen copilot to find invoices, summarize vendor spend, or explain anomalies without digging through tables.",
		eyebrow: "Finance Copilot",
		metric: "< 10s",
		metricLabel: "to answer common lookup questions",
		highlights: ["Vendor queries", "Close support", "Follow-up prompts"],
		icon: Bot,
	},
	{
		title: "Turn raw data into action",
		description:
			"Surface concrete recommendations like duplicate subscriptions, abnormal vendor spikes, and places to tighten policy.",
		eyebrow: "AI Recommendations",
		metric: "Actionable",
		metricLabel: "insights instead of dashboards alone",
		highlights: ["Savings ideas", "Behavior changes", "Priority ordering"],
		icon: Sparkles,
	},
];

export function FeaturesSection() {
	const sectionRef = useRef<HTMLElement>(null);
	const [isVisible, setIsVisible] = useState(false);

	useEffect(() => {
		const node = sectionRef.current;
		const observer = new IntersectionObserver(
			([entry]) => {
				if (entry.isIntersecting) {
					setIsVisible(true);
				}
			},
			{
				threshold: 0.1,
				rootMargin: "0px 0px -100px 0px",
			}
		);

		if (node) {
			observer.observe(node);
		}

		return () => {
			if (node) {
				observer.unobserve(node);
			}
		};
	}, []);

	return (
		<section id="features" ref={sectionRef} className="relative z-10">
			<div className="bg-white rounded-t-[3rem] pt-16 sm:pt-24 pb-16 sm:pb-24 px-4 relative overflow-hidden">
				<div className="absolute inset-0 opacity-[0.02]">
					<div
						className="absolute inset-0"
						style={{
							backgroundImage: `radial-gradient(circle at 1px 1px, rgb(0,0,0) 1px, transparent 0)`,
							backgroundSize: "24px 24px",
						}}
					></div>
				</div>

				<div className="absolute inset-0 overflow-hidden pointer-events-none">
					{[...Array(6)].map((_, i) => (
						<div
							key={i}
							className="absolute w-1 h-1 bg-slate-200 rounded-full animate-float"
							style={{
								left: `${20 + i * 15}%`,
								top: `${30 + (i % 3) * 20}%`,
								animationDelay: `${i * 0.5}s`,
								animationDuration: `${4 + i * 0.5}s`,
							}}
						></div>
					))}
				</div>

				<div className="max-w-7xl mx-auto relative">
					<div
						className={`text-center mb-12 sm:mb-20 transition-all duration-1000 ${
							isVisible
								? "opacity-100 translate-y-0"
								: "opacity-0 translate-y-8"
						}`}
					>
						<div className="inline-flex items-center px-4 py-2 rounded-full bg-slate-100 border border-slate-200 text-slate-700 text-sm font-medium mb-6">
							<ReceiptText className="mr-2 h-4 w-4 text-slate-600" />
							Finance workflows built for speed and control
						</div>
						<h2 className="text-2xl sm:text-3xl md:text-4xl lg:text-5xl font-bold text-slate-900 text-balance mb-4 sm:mb-6">
							One platform for{" "}
							<span className="bg-gradient-to-r from-slate-600 to-slate-400 bg-clip-text text-transparent">
								modern finance operations
							</span>
						</h2>
						<p className="text-base sm:text-lg md:text-xl text-slate-600 max-w-3xl mx-auto font-light leading-relaxed">
							Lumen combines capture, controls, analysis, and
							conversational access so teams can move from intake
							to insight without losing time in manual review.
						</p>
					</div>

					<div
						className={`grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-6 transition-all duration-1000 delay-300 ${
							isVisible
								? "opacity-100 translate-y-0"
								: "opacity-0 translate-y-12"
						}`}
					>
						{featureCards.map((feature, index) => {
							const Icon = feature.icon;
							return (
							<div
								key={index}
								className={`group transition-all duration-1000 ${
									feature.span ?? ""
								}`}
								style={{
									transitionDelay: isVisible
										? `${300 + index * 100}ms`
										: "0ms",
								}}
							>
								<div className="bg-white rounded-2xl p-6 sm:p-8 h-full shadow-lg hover:shadow-2xl transition-all duration-500 hover:-translate-y-2 border border-slate-200 hover:border-slate-300">
									<div className="mb-6 rounded-2xl border border-slate-200 bg-slate-50 p-4">
										<div className="flex items-start justify-between gap-4">
											<div>
												<p className="text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
													{feature.eyebrow}
												</p>
												<p className="mt-4 text-3xl font-semibold text-slate-900">
													{feature.metric}
												</p>
												<p className="mt-2 text-sm text-slate-600">
													{feature.metricLabel}
												</p>
											</div>
											<div className="rounded-2xl bg-white p-3 shadow-sm">
												<Icon className="h-5 w-5 text-slate-700" />
											</div>
										</div>
										<div className="mt-5 space-y-2">
											{feature.highlights.map((highlight) => (
												<div
													key={highlight}
													className="flex items-center justify-between rounded-xl bg-white px-3 py-2 text-sm text-slate-600"
												>
													<span>{highlight}</span>
													<div className="h-2 w-2 rounded-full bg-slate-300" />
												</div>
											))}
										</div>
									</div>

									<h3 className="text-xl sm:text-2xl font-bold text-slate-900 mb-4 group-hover:text-slate-700 transition-colors duration-300">
										{feature.title}
									</h3>

									<p className="text-slate-600 text-sm sm:text-base leading-relaxed">
										{feature.description}
									</p>
								</div>
							</div>
							);
						})}
					</div>
				</div>
			</div>
		</section>
	);
}
