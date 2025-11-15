"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Bell, TrendingUp, Calendar } from "lucide-react";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { useEffect, useState } from "react";
import { aiAnalyticsApi } from "@/lib/api/client";

const cardVariants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			duration: 0.5,
			ease: "easeOut" as const,
			delay: 0.2,
		},
	},
};

export default function ReminderDetailsCard() {
	const [reminders, setReminders] = useState<any[]>([]);
	const [isLoading, setIsLoading] = useState(true);

	useEffect(() => {
		const fetchReminders = async () => {
			try {
				const response = await aiAnalyticsApi.getReminders("123", 7);
				if (response.success) {
					setReminders(response.reminders || []);
				}
			} catch (error) {
				console.error("Failed to fetch reminders:", error);
			} finally {
				setIsLoading(false);
			}
		};

		fetchReminders();
	}, []);

	return (
		<motion.div
			variants={cardVariants}
			initial="hidden"
			animate="visible"
			className="h-full"
		>
			<Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-all duration-300 h-full flex flex-col">
				<CardHeader className="pb-3">
					<CardTitle className="text-lg font-semibold text-gray-900 flex items-center gap-2">
						<Bell className="w-5 h-5 text-blue-600" />
						Reminders & Forecasts
					</CardTitle>
				</CardHeader>
				<CardContent className="flex-1 overflow-hidden">
					{isLoading ? (
						<div className="animate-pulse space-y-3">
							<div className="h-20 bg-gray-200 rounded"></div>
							<div className="h-20 bg-gray-200 rounded"></div>
							<div className="h-20 bg-gray-200 rounded"></div>
						</div>
					) : reminders.length === 0 ? (
						<div className="text-center py-8 text-gray-500">
							No reminders or forecasts available
						</div>
					) : (
						<div className="space-y-3 h-[380px] overflow-y-auto pr-2 custom-scrollbar">
							{reminders.map((reminder, index) => (
								<motion.div
									key={reminder.id}
									initial={{ opacity: 0, x: -20 }}
									animate={{ opacity: 1, x: 0 }}
									transition={{
										duration: 0.3,
										delay: reminder.id * 0.1,
									}}
									className={`p-3 rounded-lg border-l-4 transition-all duration-200 hover:shadow-md cursor-pointer ${
										reminder.type === "upcoming"
											? "bg-orange-50 border-orange-500 hover:bg-orange-100"
											: "bg-blue-50 border-blue-500 hover:bg-blue-100"
									}`}
								>
									<div className="flex items-start justify-between mb-2">
										<div className="flex-1">
											<h4 className="font-semibold text-gray-900 text-sm">
												{reminder.vendor}
											</h4>
											<div className="flex items-center gap-2 mt-1">
												<Badge
													variant="outline"
													className={`text-xs ${
														reminder.type ===
														"upcoming"
															? "bg-orange-100 text-orange-700 border-orange-300"
															: "bg-blue-100 text-blue-700 border-blue-300"
													}`}
												>
													{reminder.type ===
													"upcoming" ? (
														<Calendar className="w-3 h-3 mr-1" />
													) : (
														<TrendingUp className="w-3 h-3 mr-1" />
													)}
													{reminder.type ===
													"upcoming"
														? "Upcoming"
														: "Forecast"}
												</Badge>
												<span className="text-xs text-gray-600">
													{reminder.category}
												</span>
											</div>
										</div>
										<div className="text-right">
											<p className="font-bold text-gray-900">
												€{reminder.amount.toFixed(2)}
											</p>
											<p className="text-xs text-gray-600">
												{reminder.date}
											</p>
										</div>
									</div>
									<p className="text-xs text-gray-600 mt-2 italic">
										{reminder.description ||
											reminder.reason}
									</p>
								</motion.div>
							))}
						</div>
					)}
				</CardContent>
			</Card>

			<style jsx global>{`
				.custom-scrollbar::-webkit-scrollbar {
					width: 6px;
				}
				.custom-scrollbar::-webkit-scrollbar-track {
					background: #f3f4f6;
					border-radius: 10px;
				}
				.custom-scrollbar::-webkit-scrollbar-thumb {
					background: #d1d5db;
					border-radius: 10px;
				}
				.custom-scrollbar::-webkit-scrollbar-thumb:hover {
					background: #9ca3af;
				}
			`}</style>
		</motion.div>
	);
}
