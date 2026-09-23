"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Bell, TrendingUp, Calendar } from "lucide-react";
import { motion } from "framer-motion";
import { Badge } from "@/components/ui/badge";
import { useState, useEffect } from "react";
import { analyticsApi } from "@/lib/api/client";

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
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchReminders = async () => {
			try {
				setError(null);
				const response = await analyticsApi.getAllTimeSummary();
				if (response.success && response.upcoming_payments) {
					setReminders(response.upcoming_payments);
				} else {
					setReminders([]);
					setError("Could not load reminders.");
				}
			} catch (err) {
				console.error("Failed to load reminders", err);
				setReminders([]);
				setError("Could not load reminders.");
			} finally {
				setLoading(false);
			}
		};
		fetchReminders();
	}, []);

	if (loading) {
		return (
			<Card className="h-full border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardContent className="flex items-center justify-center h-[300px]">
					<p className="text-muted-foreground">Loading reminders...</p>
				</CardContent>
			</Card>
		);
	}

	return (
		<motion.div
			variants={cardVariants}
			initial="hidden"
			animate="visible"
			className="h-full"
		>
			<Card className="flex h-full flex-col border-border/70 bg-card/80 shadow-lg shadow-black/10 transition-all duration-300 hover:shadow-xl hover:shadow-black/10">
				<CardHeader className="pb-3">
					<CardTitle className="flex items-center gap-2 text-lg font-semibold text-foreground">
						<Bell className="h-5 w-5 text-primary" />
						Reminders & Forecasts
					</CardTitle>
				</CardHeader>
				<CardContent className="flex-1 overflow-hidden">
					{error ? (
						<div className="py-8 text-center text-muted-foreground">
							{error}
						</div>
					) : reminders.length === 0 ? (
						<div className="py-8 text-center text-muted-foreground">
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
											? "bg-amber-500/10 border-amber-400 hover:bg-amber-500/15"
											: "bg-primary/10 border-primary hover:bg-primary/15"
									}`}
								>
									<div className="flex items-start justify-between mb-2">
										<div className="flex-1">
											<h4 className="text-sm font-semibold text-foreground">
												{reminder.vendor}
											</h4>
											<div className="flex items-center gap-2 mt-1">
												<Badge
													variant="outline"
													className={`text-xs ${
														reminder.type ===
														"upcoming"
															? "border-amber-400/30 bg-amber-500/15 text-amber-300"
															: "border-primary/30 bg-primary/15 text-primary"
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
												<span className="text-xs text-muted-foreground">
													{reminder.category}
												</span>
											</div>
										</div>
										<div className="text-right">
											<p className="font-bold text-foreground">
												₹
												{reminder.amount?.toLocaleString(
													"en-IN",
													{
														minimumFractionDigits: 2,
														maximumFractionDigits: 2,
													}
												) || "0.00"}
											</p>
											<p className="text-xs text-muted-foreground">
												{reminder.date}
											</p>
										</div>
									</div>
									<p className="mt-2 text-xs italic text-muted-foreground">
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
					background: rgba(51, 65, 85, 0.4);
					border-radius: 10px;
				}
				.custom-scrollbar::-webkit-scrollbar-thumb {
					background: rgba(148, 163, 184, 0.55);
					border-radius: 10px;
				}
				.custom-scrollbar::-webkit-scrollbar-thumb:hover {
					background: rgba(148, 163, 184, 0.8);
				}
			`}</style>
		</motion.div>
	);
}
