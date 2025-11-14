"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Bell, TrendingUp, Calendar } from "lucide-react";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";

// Mock data - Replace with API call
const mockReminders = [
	{
		id: 1,
		type: "upcoming",
		vendor: "Amazon Web Services",
		amount: 450.0,
		date: "Nov 18, 2025",
		reason: "Monthly subscription payment",
		category: "Cloud Services",
	},
	{
		id: 2,
		type: "forecast",
		vendor: "Office Supplies Inc",
		amount: 280.5,
		date: "Nov 20, 2025",
		reason: "Based on monthly purchasing pattern",
		category: "Office Supplies",
	},
	{
		id: 3,
		type: "upcoming",
		vendor: "Salesforce",
		amount: 1200.0,
		date: "Nov 22, 2025",
		reason: "Quarterly license renewal",
		category: "Software",
	},
	{
		id: 4,
		type: "forecast",
		vendor: "Electric Company",
		amount: 320.0,
		date: "Nov 25, 2025",
		reason: "Predicted utility bill based on historical data",
		category: "Utilities",
	},
	{
		id: 5,
		type: "upcoming",
		vendor: "Google Workspace",
		amount: 144.0,
		date: "Nov 28, 2025",
		reason: "Monthly team subscription",
		category: "Software",
	},
];

const cardVariants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			duration: 0.5,
			ease: "easeOut",
			delay: 0.2,
		},
	},
};

export default function ReminderDetailsCard() {
	return (
		<motion.div
			variants={cardVariants}
			initial="hidden"
			animate="visible"
			className="h-full"
		>
			<Card className="border-slate-800 shadow-lg hover:shadow-xl transition-all duration-300 bg-slate-900/50 backdrop-blur-sm h-full flex flex-col">
				<CardHeader className="pb-3">
					<CardTitle className="text-lg font-semibold text-white flex items-center gap-2">
						<Bell className="w-5 h-5 text-green-400" />
						Reminders & Forecasts
					</CardTitle>
				</CardHeader>
				<CardContent className="flex-1 overflow-hidden">
					<div className="space-y-3 h-[380px] overflow-y-auto pr-2 custom-scrollbar">
						{mockReminders.map((reminder) => (
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
										? "bg-orange-900/20 border-orange-500 hover:bg-orange-900/30"
										: "bg-blue-900/20 border-blue-500 hover:bg-blue-900/30"
								}`}
							>
								<div className="flex items-start justify-between mb-2">
									<div className="flex-1">
										<h4 className="font-semibold text-white text-sm">
											{reminder.vendor}
										</h4>
										<div className="flex items-center gap-2 mt-1">
											<Badge
												variant="outline"
												className={`text-xs ${
													reminder.type === "upcoming"
														? "bg-orange-900/50 text-orange-300 border-orange-700"
														: "bg-blue-900/50 text-blue-300 border-blue-700"
												}`}
											>
												{reminder.type ===
												"upcoming" ? (
													<Calendar className="w-3 h-3 mr-1" />
												) : (
													<TrendingUp className="w-3 h-3 mr-1" />
												)}
												{reminder.type === "upcoming"
													? "Upcoming"
													: "Forecast"}
											</Badge>
											<span className="text-xs text-slate-400">
												{reminder.category}
											</span>
										</div>
									</div>
									<div className="text-right">
										<p className="font-bold text-white">
											€{reminder.amount.toFixed(2)}
										</p>
										<p className="text-xs text-slate-300">
											{reminder.date}
										</p>
									</div>
								</div>
								<p className="text-xs text-slate-300 mt-2 italic">
									{reminder.reason}
								</p>
							</motion.div>
						))}
					</div>
				</CardContent>
			</Card>

			<style jsx global>{`
				.custom-scrollbar::-webkit-scrollbar {
					width: 6px;
				}
				.custom-scrollbar::-webkit-scrollbar-track {
					background: #1e293b;
					border-radius: 10px;
				}
				.custom-scrollbar::-webkit-scrollbar-thumb {
					background: #475569;
					border-radius: 10px;
				}
				.custom-scrollbar::-webkit-scrollbar-thumb:hover {
					background: #64748b;
				}
			`}</style>
		</motion.div>
	);
}
