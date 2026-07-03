// @ts-nocheck
"use client";

import { useState, useEffect, useRef } from "react";
import { MessageCircle, Clock, Zap } from "lucide-react";
import Image from "next/image";

import { logger } from "@/lib/logger";
const conversations = [
	{
		title: "Invoice Data Extraction Query",
		messages: [
			{
				text: "Hi! I just uploaded an invoice but some fields look incorrect. Can you help?",
				sender: "customer",
				delay: 0,
			},
			{
				text: "I'd be happy to help! I can see the invoice you uploaded. Which specific fields are you concerned about?",
				sender: "ai",
				delay: 1000,
			},
			{
				text: "The vendor name shows 'TechSupply Co' but it should be 'TechSupply Corporation'. Can you fix this?",
				sender: "customer",
				delay: 2500,
			},
			{
				text: "I've updated the vendor name to 'TechSupply Corporation'. I can also see the total amount is €1,245.50 with invoice date December 15, 2024. Does everything else look correct?",
				sender: "ai",
				delay: 3500,
			},
			{
				text: "Perfect! What's my total spending with TechSupply this quarter?",
				sender: "customer",
				delay: 5000,
			},
			{
				text: "You've spent €8,450.75 with TechSupply Corporation in Q4 2024 across 7 invoices. Would you like to see a breakdown by category or month?",
				sender: "ai",
				delay: 6000,
			},
			{
				text: "No, that's exactly what I needed. Thanks!",
				sender: "customer",
				delay: 7500,
			},
			{
				text: "You're welcome! Feel free to ask if you need insights about any other vendors or spending patterns.",
				sender: "ai",
				delay: 8500,
			},
		],
	},
	{
		title: "Spending Pattern Analysis",
		messages: [
			{
				text: "What are my top 3 expense categories this month?",
				sender: "customer",
				delay: 0,
			},
			{
				text: "Your top 3 expense categories in December are: 1) Office Supplies (€12,450) 2) Software Licenses (€8,900) 3) Equipment (€6,750). Total spending is up 15% compared to November.",
				sender: "ai",
				delay: 1000,
			},
			{
				text: "That's higher than expected. Any recurring charges I should review?",
				sender: "customer",
				delay: 2500,
			},
			{
				text: "I've identified 3 duplicate software subscriptions totaling €450/month. You're also paying for CloudStorage Pro at €89/month but only using 15% of your allocated space.",
				sender: "ai",
				delay: 4000,
			},
			{
				text: "Can you show me which subscriptions are duplicates?",
				sender: "customer",
				delay: 5500,
			},
			{
				text: "You have Zoom Business at €299, Zoom Pro at €149, and a legacy Zoom account at €45. I recommend consolidating to a single Business plan. Would you like me to flag these for review?",
				sender: "ai",
				delay: 6500,
			},
		],
	},
	{
		title: "Late Night Invoice Question",
		messages: [
			{
				text: "Hi, it's 11 PM. I need to find all invoices from OfficeMax for our tax filing. How quickly can you pull this?",
				sender: "customer",
				delay: 0,
			},
			{
				text: "I can help right away! I found 23 invoices from OfficeMax in 2024. Would you like them grouped by quarter or exported as a single report?",
				sender: "ai",
				delay: 1000,
			},
			{
				text: "Grouped by quarter please. What's the total for the year?",
				sender: "customer",
				delay: 2500,
			},
			{
				text: "Q1: €4,230, Q2: €5,890, Q3: €4,560, Q4: €6,120. Total annual spending with OfficeMax: €20,800. I'm preparing a detailed PDF report now.",
				sender: "ai",
				delay: 3500,
			},
			{
				text: "Perfect! Can you also show me spending trends year-over-year?",
				sender: "customer",
				delay: 5000,
			},
			{
				text: "Your OfficeMax spending increased 18% from 2023. The report is ready and includes comparison charts. Check your email - I've just sent it!",
				sender: "ai",
				delay: 6000,
			},
		],
	},
];

export function AITeamSection() {
	const sectionRef = useRef<HTMLElement>(null); // Added section ref for intersection observer
	const [isVisible, setIsVisible] = useState(false);
	const [currentConversation, setCurrentConversation] = useState(0);
	const [displayedMessages, setDisplayedMessages] = useState<any[]>([]);
	const [isTyping, setIsTyping] = useState(false);
	const timeoutRef = useRef<NodeJS.Timeout | null>(null);
	const chatContainerRef = useRef<HTMLDivElement>(null);

	useEffect(() => {
		const node = sectionRef.current;
		const observer = new IntersectionObserver(
			([entry]) => {
				if (entry.isIntersecting) {
					logger.debug("[v0] AI Team Section is now visible");
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

	useEffect(() => {
		if (chatContainerRef.current) {
			chatContainerRef.current.scrollTop =
				chatContainerRef.current.scrollHeight;
		}
	}, [displayedMessages, isTyping]);

	useEffect(() => {
		const conversation = conversations[currentConversation];
		setDisplayedMessages([]);
		setIsTyping(false);

		// Clear any existing timeout
		if (timeoutRef.current) {
			clearTimeout(timeoutRef.current);
		}

		let messageIndex = 0;

		const showNextMessage = () => {
			if (messageIndex >= conversation.messages.length) {
				// Wait 3 seconds then move to next conversation
				timeoutRef.current = setTimeout(() => {
					setCurrentConversation(
						(prev) => (prev + 1) % conversations.length
					);
				}, 3000);
				return;
			}

			const message = conversation.messages[messageIndex];

			timeoutRef.current = setTimeout(() => {
				if (message.sender === "ai") {
					setIsTyping(true);
					timeoutRef.current = setTimeout(() => {
						setDisplayedMessages((prev) => [...prev, message]);
						setIsTyping(false);
						messageIndex++;
						showNextMessage();
					}, 800); // Reduced typing delay from 1500ms to 800ms for faster replies
				} else {
					setDisplayedMessages((prev) => [...prev, message]);
					messageIndex++;
					showNextMessage();
				}
			}, message.delay);
		};

		showNextMessage();

		// Cleanup timeout on unmount or conversation change
		return () => {
			if (timeoutRef.current) {
				clearTimeout(timeoutRef.current);
			}
		};
	}, [currentConversation]);

	return (
		<section id="ai-team" ref={sectionRef} className="relative z-10">
			<div className="bg-white rounded-b-[3rem] pt-16 sm:pt-24 pb-16 sm:pb-24 px-4 relative overflow-hidden">
				<div className="container mx-auto px-4 relative z-10">
					<div className="text-center mb-16">
						<div
							className={`inline-flex items-center gap-2 bg-slate-50 border border-slate-200 text-slate-700 px-4 py-2 rounded-full text-sm font-medium mb-6 transition-all duration-1000 ${
								isVisible
									? "opacity-100 translate-y-0"
									: "opacity-0 translate-y-8"
							}`}
						>
							<MessageCircle className="w-4 h-4" />
							Finance Copilot Demo
						</div>

						<h2
							className={`text-4xl md:text-5xl font-bold text-slate-900 mb-4 transition-all duration-1000 delay-200 ${
								isVisible
									? "opacity-100 translate-y-0"
									: "opacity-0 translate-y-8"
							}`}
						>
							See Lumen Handle{" "}
							<span className="bg-gradient-to-r from-slate-600 to-slate-400 bg-clip-text text-transparent">
								Real Finance Questions
							</span>
						</h2>

						<p
							className={`text-xl text-slate-600 max-w-2xl mx-auto transition-all duration-1000 delay-400 ${
								isVisible
									? "opacity-100 translate-y-0"
									: "opacity-0 translate-y-8"
							}`}
						>
							Watch how the copilot explains spend, follows up on
							vendors, and helps finance teams move faster without
							losing audit context.
						</p>
					</div>

					<div className="flex flex-col lg:flex-row items-center gap-12 lg:gap-20 max-w-7xl mx-auto">
						{/* Left side - Text content */}
						<div className="w-full lg:w-1/2 flex flex-col justify-center lg:h-[600px] space-y-6 lg:space-y-8 order-2 lg:order-1">
							<div
								className={`transition-all duration-1000 delay-600 ${
									isVisible
										? "opacity-100 translate-x-0"
										: "opacity-0 -translate-x-8"
								}`}
							>
								<h3 className="text-2xl lg:text-3xl font-bold text-slate-900 mb-4 lg:mb-6">
									Finance answers without dashboard hunting
								</h3>

								<div className="space-y-3 lg:space-y-4 text-base lg:text-lg text-slate-700 leading-relaxed">
									<p>
										Lumen turns stored transactions into a
										working conversation layer for your
										finance team.
									</p>

									<p>
										Use it to chase down vendor totals,
										summarize unusual spikes, or prepare for
										close without pulling raw exports first.
									</p>

									<p className="text-lg lg:text-xl font-semibold text-slate-900">
										When questions are answered faster,
										approvals and reporting move faster too.
									</p>
								</div>
							</div>

							<div
								className={`transition-all duration-1000 delay-800 ${
									isVisible
										? "opacity-100 translate-x-0"
										: "opacity-0 -translate-x-8"
								}`}
							>
								<div className="p-4 lg:p-6 bg-slate-50 rounded-xl border-l-4 border-slate-900">
									<p className="text-slate-800 font-medium text-sm lg:text-base">
										"Our AP team now gets the answer before
										the follow-up email is drafted. Vendor
										explanations, anomaly checks, and
										spending summaries are all one prompt
										away."
									</p>
									<p className="text-xs lg:text-sm text-slate-600 mt-2">
										— Priya Nair, Head of Finance Operations
									</p>
								</div>
							</div>
						</div>

						{/* Right side - Phone mockup */}
						<div className="w-full lg:w-1/2 flex justify-center order-1 lg:order-2">
							<div className="max-w-md w-full">
								<div
									className={`relative transition-all duration-1000 delay-600 ${
										isVisible
											? "opacity-100 translate-y-0"
											: "opacity-0 translate-y-8"
									}`}
								>
									<div className="bg-slate-900 rounded-[2.5rem] p-2 shadow-2xl">
										<div className="bg-black rounded-[2rem] p-1">
											<div className="bg-white rounded-[1.5rem] overflow-hidden">
												{/* Status bar */}
												<div className="bg-slate-50 px-6 py-3 flex justify-between items-center text-sm">
													<div className="flex items-center gap-1">
														<div className="w-2 h-2 bg-slate-900 rounded-full"></div>
														<span className="font-medium text-slate-700">
															Lumen AI Assistant
														</span>
													</div>
													<div className="flex items-center gap-1 text-slate-500">
														<Clock className="w-3 h-3" />
														<span className="text-xs">
															24/7
														</span>
													</div>
												</div>

												<div className="bg-slate-900 px-6 py-4 text-white">
													<div className="flex items-center gap-3">
														<Image
															src="/images/michael-ai-agent.jpg"
															alt="Michael - AI Agent"
															width={32}
															height={32}
															className="mr-2 mt-1 h-8 w-8 flex-shrink-0 rounded-full object-cover"
														/>
														<div className="flex-1">
															<h3 className="font-semibold text-sm">
																Lumen - AI
																Finance
																Assistant
															</h3>
															<p className="text-xs text-slate-300">
																Ask me anything
																about your
																invoices
															</p>
														</div>
														<div className="text-xs text-green-400 flex items-center gap-1">
															<div className="w-2 h-2 bg-green-400 rounded-full"></div>
															Online
														</div>
													</div>
												</div>

												{/* Chat messages */}
												<div
													ref={chatContainerRef}
													className="h-96 overflow-y-scroll scrollbar-hide p-4 space-y-3 bg-slate-50"
													style={{
														scrollbarWidth: "none",
														msOverflowStyle: "none",
													}}
												>
													{displayedMessages.map(
														(message, index) => (
															<div
																key={index}
																className={`flex ${
																	message.sender ===
																	"customer"
																		? "justify-end"
																		: "justify-start"
																}`}
															>
																{message.sender ===
																	"ai" && (
																	<Image
																		src="/images/michael-ai-agent.jpg"
																		alt="Michael"
																		width={24}
																		height={24}
																		className="mr-2 mt-1 h-6 w-6 flex-shrink-0 rounded-full object-cover"
																	/>
																)}
																<div
																	className={`max-w-[80%] p-3 rounded-2xl text-sm leading-relaxed ${
																		message.sender ===
																		"customer"
																			? "bg-slate-900 text-white rounded-br-md"
																			: "bg-white text-slate-800 shadow-sm border border-slate-200 rounded-bl-md"
																	}`}
																>
																	{message.text
																		.split(
																			"\n"
																		)
																		.map(
																			(
																				line,
																				i
																			) => (
																				<div
																					key={
																						i
																					}
																				>
																					{
																						line
																					}
																				</div>
																			)
																		)}
																</div>
																{message.sender ===
																	"customer" && (
																	<div className="w-6 h-6 rounded-full bg-slate-400 ml-2 mt-1 flex-shrink-0 flex items-center justify-center text-xs text-white font-medium">
																		C
																	</div>
																)}
															</div>
														)
													)}

													{/* Typing indicator */}
													{isTyping && (
														<div className="flex justify-start items-start">
															<Image
																src="/images/michael-ai-agent.jpg"
																alt="Michael"
																width={24}
																height={24}
																className="mr-2 mt-1 h-6 w-6 flex-shrink-0 rounded-full object-cover"
															/>
															<div className="bg-white p-3 rounded-2xl rounded-bl-md shadow-sm border border-slate-200">
																<div className="flex space-x-1">
																	<div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"></div>
																	<div
																		className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
																		style={{
																			animationDelay:
																				"0.1s",
																		}}
																	></div>
																	<div
																		className="w-2 h-2 bg-slate-400 rounded-full animate-bounce"
																		style={{
																			animationDelay:
																				"0.2s",
																		}}
																	></div>
																</div>
															</div>
														</div>
													)}
												</div>

												<div className="p-4 bg-white border-t border-slate-200">
													<div className="flex items-center gap-3 bg-slate-100 rounded-full px-4 py-2">
														<span className="text-slate-500 text-sm lg:text-base flex-1">
															Lumen is
															analyzing...
														</span>
														<div className="w-6 h-6 bg-slate-900 rounded-full flex items-center justify-center">
															<Zap className="w-3 h-3 text-white" />
														</div>
													</div>
												</div>
											</div>
										</div>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</div>
		</section>
	);
}
