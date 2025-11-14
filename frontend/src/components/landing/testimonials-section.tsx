"use client";

import { useEffect, useRef } from "react";
import { TestimonialsColumn } from "@/components/ui/testimonials-column";

export function TestimonialsSection() {
	const sectionRef = useRef<HTMLElement>(null);

	useEffect(() => {
		const observer = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (entry.isIntersecting) {
						const elements =
							entry.target.querySelectorAll(".fade-in-element");
						elements.forEach((element, index) => {
							setTimeout(() => {
								element.classList.add("animate-fade-in-up");
							}, index * 300);
						});
					}
				});
			},
			{ threshold: 0.1 }
		);

		if (sectionRef.current) {
			observer.observe(sectionRef.current);
		}

		return () => observer.disconnect();
	}, []);

	const testimonials = [
		{
			text: "We went from spending 8+ hours weekly on manual invoice processing to instant automated extraction. Processing time reduced by 80% in the first month.",
			name: "Mike Rodriguez",
			role: "Finance Director",
		},
		{
			text: "We spend so much less time on data entry and can focus on strategic financial analysis. Lumen's OCR accuracy is remarkable.",
			name: "Sarah Chen",
			role: "Accounting Manager",
		},
		{
			text: "With Lumen, our invoice processing efficiency increased by 85% and we identified €12,000 in duplicate subscriptions within the first quarter.",
			name: "Michael Torres",
			role: "CFO",
		},
		{
			text: "The AI chatbot answers spending questions instantly, so our team never wastes time searching through old invoices. Real-time analytics are game-changing.",
			name: "Jennifer Walsh",
			role: "Operations Director",
		},
		{
			text: "Financial reporting became effortless since implementing Lumen. The automated insights help us make better purchasing decisions and negotiate with vendors.",
			name: "David Kim",
			role: "Procurement Manager",
		},
		{
			text: "Our retail operations saw immediate ROI. Invoice data extraction is 95%+ accurate, and the spending analytics revealed opportunities for 15% cost savings.",
			name: "Lisa Thompson",
			role: "Retail Finance Lead",
		},
		{
			text: "Invoice management was a bottleneck until Lumen. Now we process 3x more invoices with the same team size, and audit preparation is painless.",
			name: "James Wilson",
			role: "Controller",
		},
		{
			text: "Month-end close time reduced by 45% with automated invoice processing. The AI identifies anomalies before they become problems.",
			name: "Maria Garcia",
			role: "Senior Accountant",
		},
	];

	return (
		<section
			id="testimonials"
			ref={sectionRef}
			className="relative pt-16 pb-16 px-4 sm:px-6 lg:px-8"
		>
			{/* Grid Background */}
			<div className="absolute inset-0 opacity-10">
				<div
					className="h-full w-full"
					style={{
						backgroundImage: `
            linear-gradient(rgba(255,255,255,0.1) 1px, transparent 1px),
            linear-gradient(90deg, rgba(255,255,255,0.1) 1px, transparent 1px)
          `,
						backgroundSize: "80px 80px",
					}}
				/>
			</div>

			<div className="relative max-w-7xl mx-auto">
				{/* Header Section - Keep as user loves it */}
				<div className="text-center mb-16 md:mb-32">
					<div className="fade-in-element opacity-0 translate-y-8 transition-all duration-1000 ease-out inline-flex items-center gap-2 text-white/60 text-sm font-medium tracking-wider uppercase mb-6">
						<div className="w-8 h-px bg-white/30"></div>
						Success Stories
						<div className="w-8 h-px bg-white/30"></div>
					</div>
					<h2 className="fade-in-element opacity-0 translate-y-8 transition-all duration-1000 ease-out text-5xl md:text-6xl lg:text-7xl font-light text-white mb-8 tracking-tight text-balance">
						The businesses we{" "}
						<span className="font-medium italic">empower</span>
					</h2>
					<p className="fade-in-element opacity-0 translate-y-8 transition-all duration-1000 ease-out text-xl text-white/70 max-w-2xl mx-auto leading-relaxed">
						Discover how leading businesses are transforming their
						invoice management with AI-powered automation
					</p>
				</div>

				{/* Testimonials Carousel */}
				<div className="fade-in-element opacity-0 translate-y-8 transition-all duration-1000 ease-out relative flex justify-center items-center min-h-[600px] md:min-h-[800px] overflow-hidden">
					<div
						className="flex gap-8 max-w-6xl"
						style={{
							maskImage:
								"linear-gradient(to bottom, transparent 0%, black 10%, black 90%, transparent 100%)",
							WebkitMaskImage:
								"linear-gradient(to bottom, transparent 0%, black 10%, black 90%, transparent 100%)",
						}}
					>
						<TestimonialsColumn
							testimonials={testimonials.slice(0, 3)}
							duration={15}
							className="flex-1"
						/>
						<TestimonialsColumn
							testimonials={testimonials.slice(2, 5)}
							duration={12}
							className="flex-1 hidden md:block"
						/>
						<TestimonialsColumn
							testimonials={testimonials.slice(1, 4)}
							duration={18}
							className="flex-1 hidden lg:block"
						/>
					</div>
				</div>
			</div>
		</section>
	);
}
