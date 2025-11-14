"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";

interface Testimonial {
	text: string;
	name: string;
	role: string;
}

interface TestimonialsColumnProps {
	testimonials: Testimonial[];
	duration?: number;
	className?: string;
}

export function TestimonialsColumn({
	testimonials,
	duration = 15,
	className,
}: TestimonialsColumnProps) {
	const columnRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		if (!columnRef.current) return;

		const column = columnRef.current;
		const scrollHeight = column.scrollHeight / 2;

		let animationFrame: number;
		let currentScroll = 0;

		const animate = () => {
			currentScroll += 0.5;
			if (currentScroll >= scrollHeight) {
				currentScroll = 0;
			}
			column.scrollTop = currentScroll;
			animationFrame = requestAnimationFrame(animate);
		};

		animationFrame = requestAnimationFrame(animate);

		return () => {
			cancelAnimationFrame(animationFrame);
		};
	}, [duration]);

	const duplicatedTestimonials = [...testimonials, ...testimonials];

	return (
		<div
			ref={columnRef}
			className={cn("overflow-hidden h-[600px] md:h-[800px]", className)}
		>
			<div className="flex flex-col gap-6">
				{duplicatedTestimonials.map((testimonial, index) => (
					<div
						key={index}
						className="bg-white/5 backdrop-blur-md border border-white/10 rounded-2xl p-8 hover:bg-white/10 transition-all duration-300 hover:scale-[1.02] hover:border-white/20 group"
					>
						<p className="text-white/90 text-lg leading-relaxed mb-6 group-hover:text-white transition-colors">
							&ldquo;{testimonial.text}&rdquo;
						</p>
						<div className="flex items-center gap-4">
							<div className="w-12 h-12 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-white font-semibold text-lg">
								{testimonial.name.charAt(0)}
							</div>
							<div>
								<p className="text-white font-medium">
									{testimonial.name}
								</p>
								<p className="text-white/60 text-sm">
									{testimonial.role}
								</p>
							</div>
						</div>
					</div>
				))}
			</div>
		</div>
	);
}
