"use client";

import { useState, useEffect } from "react";
import { Slider } from "@/components/ui/slider";
import {
	Select,
	SelectContent,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "@/components/ui/select";
import { Card } from "@/components/ui/card";
import { TrendingUp, ReceiptText, DollarSign, Clock } from "lucide-react";

interface CalculatorInputs {
	monthlyInvoices: number;
	minutesPerInvoice: number;
	hourlyCost: number;
	workflowProfile: string;
}

export function ROICalculatorSection() {
	const [inputs, setInputs] = useState<CalculatorInputs>({
		monthlyInvoices: 480,
		minutesPerInvoice: 14,
		hourlyCost: 38,
		workflowProfile: "growing-finance-team",
	});

	const [isVisible, setIsVisible] = useState(false);

	useEffect(() => {
		const observer = new IntersectionObserver(
			(entries) => {
				entries.forEach((entry) => {
					if (entry.isIntersecting) {
						setIsVisible(true);
					}
				});
			},
			{ threshold: 0.1 }
		);

		const section = document.getElementById("roi-calculator");
		if (section) {
			observer.observe(section);
		}

		return () => observer.disconnect();
	}, []);

	const getWorkflowProfile = () => {
		const profiles = {
			"lean-ap": {
				timeSaved: 58,
				accuracy: 94,
				fasterClose: 2,
				exceptionsReduced: 18,
			},
			"growing-finance-team": {
				timeSaved: 67,
				accuracy: 96,
				fasterClose: 3,
				exceptionsReduced: 24,
			},
			"multi-entity-ops": {
				timeSaved: 74,
				accuracy: 97,
				fasterClose: 5,
				exceptionsReduced: 31,
			},
		} as const;

		return profiles[
			inputs.workflowProfile as keyof typeof profiles
		];
	};

	const profile = getWorkflowProfile();
	const currentHours =
		(inputs.monthlyInvoices * inputs.minutesPerInvoice) / 60;
	const automatedHours =
		currentHours * (1 - profile.timeSaved / 100);
	const hoursSaved = currentHours - automatedHours;
	const monthlySavings = hoursSaved * inputs.hourlyCost;
	const annualSavings = monthlySavings * 12;
	const invoicesPerDay = Math.round(inputs.monthlyInvoices / 22);
	const hoursRecoveredPerWeek = hoursSaved / 4.3;

	return (
		<section id="roi-calculator" className="py-16 md:py-20 px-4 relative">
			<div className="max-w-6xl mx-auto">
				{/* Header */}
				<div
					className={`text-center mb-12 md:mb-16 transition-all duration-700 ${
						isVisible
							? "opacity-100 translate-y-0"
							: "opacity-0 translate-y-8"
					}`}
				>
					<div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10 backdrop-blur-sm mb-6">
						<TrendingUp className="w-4 h-4 text-primary" />
						<span className="text-sm font-medium text-white/80">
							Operations Calculator
						</span>
					</div>

					<h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-white mb-4 md:mb-6 text-balance">
						Estimate your potential{" "}
						<span className="bg-gradient-to-r from-white to-gray-300 bg-clip-text text-transparent">
							AP time savings
						</span>
					</h2>

					<p className="text-lg md:text-xl text-gray-300 max-w-2xl mx-auto text-balance">
						Model how much manual invoice handling your team can
						remove each month with automated capture, validation,
						and guided review.
					</p>
				</div>

				<div className="grid lg:grid-cols-2 gap-8 lg:gap-10 items-stretch">
					{/* Calculator Inputs */}
					<div
						className={`transition-all duration-700 delay-200 ${
							isVisible
								? "opacity-100 translate-y-0"
								: "opacity-0 translate-y-8"
						}`}
					>
						<Card className="p-6 md:p-8 bg-[radial-gradient(35%_128px_at_50%_0%,theme(backgroundColor.white/15%),theme(backgroundColor.white/5%))] border-white/20 backdrop-blur-sm shadow-2xl h-full flex flex-col">
							<h3 className="text-xl md:text-2xl font-semibold text-white mb-6 md:mb-8">
								Your Current Workflow
							</h3>

							<div className="space-y-8 flex-1">
								{/* Business Type */}
								<div>
									<label className="block text-sm font-medium text-gray-300 mb-3">
										Workflow Profile
									</label>
									<Select
										value={inputs.workflowProfile}
										onValueChange={(value) =>
											setInputs((prev) => ({
												...prev,
												workflowProfile: value,
											}))
										}
									>
										<SelectTrigger className="bg-gray-700/50 border-gray-600 text-white">
											<SelectValue />
										</SelectTrigger>
										<SelectContent className="bg-gray-800 border-gray-700">
											<SelectItem value="lean-ap">
												Lean AP team
											</SelectItem>
											<SelectItem value="growing-finance-team">
												Growing finance team
											</SelectItem>
											<SelectItem value="multi-entity-ops">
												Multi-entity operations
											</SelectItem>
										</SelectContent>
									</Select>
								</div>

								{/* Monthly Invoices */}
								<div>
									<label className="block text-sm font-medium text-gray-300 mb-3">
										Monthly Invoices Reviewed:{" "}
										<span className="text-white font-semibold">
											{inputs.monthlyInvoices.toLocaleString()}
										</span>
									</label>
									<Slider
										value={[inputs.monthlyInvoices]}
										onValueChange={([value]) =>
											setInputs((prev) => ({
												...prev,
												monthlyInvoices: value,
											}))
										}
										max={5000}
										min={50}
										step={10}
										className="w-full"
									/>
									<div className="flex justify-between text-xs text-gray-400 mt-1">
										<span>50</span>
										<span>5K</span>
									</div>
								</div>

								{/* Processing Time */}
								<div>
									<label className="block text-sm font-medium text-gray-300 mb-3">
										Minutes per Invoice (Manual):{" "}
										<span className="text-white font-semibold">
											{inputs.minutesPerInvoice}
										</span>
									</label>
									<Slider
										value={[inputs.minutesPerInvoice]}
										onValueChange={([value]) =>
											setInputs((prev) => ({
												...prev,
												minutesPerInvoice: value,
											}))
										}
										max={30}
										min={4}
										step={1}
										className="w-full"
									/>
									<div className="flex justify-between text-xs text-gray-400 mt-1">
										<span>5 min</span>
										<span>30 min</span>
									</div>
								</div>

								{/* Hourly Labor Cost */}
								<div>
									<label className="block text-sm font-medium text-gray-300 mb-3">
										Blended Hourly Review Cost:{" "}
										<span className="text-white font-semibold">
											₹
											{inputs.hourlyCost.toLocaleString()}
										</span>
									</label>
									<Slider
										value={[inputs.hourlyCost]}
										onValueChange={([value]) =>
											setInputs((prev) => ({
												...prev,
												hourlyCost: value,
											}))
										}
										max={150}
										min={15}
										step={5}
										className="w-full"
									/>
									<div className="flex justify-between text-xs text-gray-400 mt-1">
										<span>₹15</span>
										<span>₹150</span>
									</div>
								</div>

								<div className="flex-1"></div>
							</div>

							<div className="mt-6 lg:hidden">
								<div className="flex items-center justify-center gap-2 p-3 rounded-lg bg-primary/10 border border-primary/20">
									<div className="animate-bounce">
										<svg
											className="w-4 h-4 text-primary"
											fill="none"
											stroke="currentColor"
											viewBox="0 0 24 24"
										>
											<path
												strokeLinecap="round"
												strokeLinejoin="round"
												strokeWidth={2}
												d="M19 14l-7 7m0 0l-7-7m7 7V3"
											/>
										</svg>
									</div>
									<span className="text-sm text-primary font-medium">
										Scroll down to see your results
									</span>
								</div>
							</div>

							<div className="mt-8 pt-6 border-t border-gray-700/50">
								<div className="space-y-4">
									<h4 className="text-sm font-semibold text-gray-300 mb-3">
										Benchmark assumptions
									</h4>
									<div className="space-y-3">
										<div className="flex items-start gap-3 p-3 rounded-lg bg-white/5">
											<div className="w-2 h-2 rounded-full bg-primary mt-2 flex-shrink-0"></div>
											<div>
												<p className="text-sm text-gray-300">
													<span className="font-medium text-white">
														Automation lift:
													</span>{" "}
													Teams like yours typically
													reduce manual handling by{" "}
													{profile.timeSaved}% after
													adoption
												</p>
											</div>
										</div>
										<div className="flex items-start gap-3 p-3 rounded-lg bg-white/5">
											<div className="w-2 h-2 rounded-full bg-primary mt-2 flex-shrink-0"></div>
											<div>
												<p className="text-sm text-gray-300">
													<span className="font-medium text-white">
														Data quality:
													</span>{" "}
													Expected extraction accuracy
													is around {profile.accuracy}%
												</p>
											</div>
										</div>
										<div className="flex items-start gap-3 p-3 rounded-lg bg-white/5">
											<div className="w-2 h-2 rounded-full bg-primary mt-2 flex-shrink-0"></div>
											<div>
												<p className="text-sm text-gray-300">
													<span className="font-medium text-white">
														Close acceleration:
													</span>{" "}
													Month-end close often moves{" "}
													{profile.fasterClose} days
													faster with cleaner intake
												</p>
											</div>
										</div>
									</div>
								</div>
							</div>
						</Card>
					</div>

					{/* Results */}
					<div
						className={`transition-all duration-700 delay-400 ${
							isVisible
								? "opacity-100 translate-y-0"
								: "opacity-0 translate-y-8"
						}`}
					>
						<Card className="p-6 md:p-8 bg-[radial-gradient(35%_128px_at_50%_0%,theme(backgroundColor.white/15%),theme(backgroundColor.white/5%))] border-white/20 backdrop-blur-sm shadow-2xl h-full flex flex-col">
							<h3 className="text-xl md:text-2xl font-semibold text-white mb-6 md:mb-8">
								Projected Impact with Lumen
							</h3>

							<div className="space-y-6 flex-1">
								{/* Current vs New Metrics */}
								<div className="grid grid-cols-2 gap-3 md:gap-4">
									<div className="text-center p-3 md:p-4 rounded-lg bg-gray-700/30">
										<div className="text-xs md:text-sm text-gray-400 mb-1">
											Current
										</div>
										<div className="text-xl md:text-2xl font-bold text-white">
											{currentHours.toFixed(0)}
										</div>
										<div className="text-xs text-gray-400">
											hours/month
										</div>
									</div>
									<div className="text-center p-3 md:p-4 rounded-lg bg-white/10 border border-white/20">
										<div className="text-xs md:text-sm text-gray-300 mb-1">
											With Lumen
										</div>
										<div className="text-xl md:text-2xl font-bold text-white">
											{automatedHours.toFixed(0)}
										</div>
										<div className="text-xs text-gray-300">
											hours/month
										</div>
									</div>
								</div>

								<div className="space-y-3 md:space-y-4">
									<div className="flex items-center justify-between p-3 md:p-4 rounded-lg bg-white/5 border border-white/10">
										<div className="flex items-center gap-3">
											<Clock className="w-4 h-4 md:w-5 md:h-5 text-gray-300" />
											<span className="text-sm md:text-base text-white">
											Time Saved
											</span>
										</div>
										<span className="text-lg md:text-xl font-bold text-white">
										{hoursRecoveredPerWeek.toFixed(1)} hrs/week
										</span>
									</div>

									<div className="flex items-center justify-between p-3 md:p-4 rounded-lg bg-white/5 border border-white/10">
										<div className="flex items-center gap-3">
											<DollarSign className="w-4 h-4 md:w-5 md:h-5 text-gray-300" />
											<span className="text-sm md:text-base text-white">
											Labor Savings
											</span>
										</div>
										<span className="text-lg md:text-xl font-bold text-white">
										₹{monthlySavings.toLocaleString()}
										</span>
									</div>

									<div className="flex items-center justify-between p-3 md:p-4 rounded-lg bg-white/5 border border-white/10">
										<div className="flex items-center gap-3">
											<TrendingUp className="w-4 h-4 md:w-5 md:h-5 text-gray-300" />
											<span className="text-sm md:text-base text-white">
											Exceptions Reduced
											</span>
										</div>
										<span className="text-lg md:text-xl font-bold text-white">
										{profile.exceptionsReduced}%
										</span>
									</div>

									<div className="flex items-center justify-between p-3 md:p-4 rounded-lg bg-white/5 border border-white/10">
										<div className="flex items-center gap-3">
										<ReceiptText className="w-4 h-4 md:w-5 md:h-5 text-gray-300" />
											<span className="text-sm md:text-base text-white">
											Daily Volume
											</span>
										</div>
										<span className="text-lg md:text-xl font-bold text-white">
										~{invoicesPerDay} invoices/day
										</span>
									</div>
								</div>

								{/* Annual Projection */}
								<div className="mt-6 md:mt-8 p-4 md:p-6 rounded-lg bg-white/5 border border-white/10">
									<div className="text-center">
										<div className="text-xs md:text-sm text-gray-300 mb-2">
											Projected Annual Labor Savings
										</div>
										<div className="text-2xl md:text-3xl lg:text-4xl font-bold text-white mb-2">
											₹{annualSavings.toLocaleString()}
										</div>
										<div className="text-xs md:text-sm text-gray-400">
											Based on your current invoice load,
											review time, and workflow benchmark
										</div>
									</div>
								</div>
							</div>
						</Card>
					</div>
				</div>

				{/* CTA */}
				<div
					className={`text-center mt-12 md:mt-16 transition-all duration-700 delay-600 ${
						isVisible
							? "opacity-100 translate-y-0"
							: "opacity-0 translate-y-8"
					}`}
				>
					<p className="text-sm text-gray-400 mt-4">
						* Estimates use conservative workflow benchmarks and
						should be validated against your internal process data.
					</p>
				</div>
			</div>
		</section>
	);
}
