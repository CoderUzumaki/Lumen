"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, DollarSign, Calendar, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";
import { useEffect, useState } from "react";

// Mock data - Replace with API call
const mockStats = {
	annualSpending: 245680.5,
	monthlyAverage: 20473.38,
	lastMonthSpending: 18234.67,
	changePercentage: 12.3,
	upcomingPayments: 7,
	overduePayments: 2,
};

const cardVariants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			duration: 0.5,
			ease: "easeOut",
		},
	},
};

export default function QuickStatsCard() {
	const [stats, setStats] = useState(mockStats);
	const [isLoading, setIsLoading] = useState(true);

	useEffect(() => {
		// Simulate API call
		setTimeout(() => {
			setStats(mockStats);
			setIsLoading(false);
		}, 300);
	}, []);

	return (
		<motion.div variants={cardVariants} initial="hidden" animate="visible">
			<Card className="border-slate-800 shadow-lg hover:shadow-xl transition-all duration-300 bg-slate-900/50 backdrop-blur-sm">
				<CardHeader className="pb-3">
					<CardTitle className="text-lg font-semibold text-white flex items-center gap-2">
						<DollarSign className="w-5 h-5 text-blue-400" />
						Quick Stats
					</CardTitle>
				</CardHeader>
				<CardContent className="space-y-4">
					{/* Annual Spending */}
					<div className="space-y-1">
						<p className="text-sm text-slate-300">
							Annual Spending (YTD)
						</p>
						<p className="text-3xl font-bold text-white">
							€{stats.annualSpending.toLocaleString()}
						</p>
						<div className="flex items-center gap-1 text-xs">
							<TrendingUp className="w-3 h-3 text-green-600" />
							<span className="text-green-600 font-medium">
								+{stats.changePercentage}%
							</span>
							<span className="text-slate-500">
								from last month
							</span>
						</div>
					</div>

					{/* Divider */}
					<div className="border-t border-slate-700"></div>

					{/* Quick Metrics Grid */}
					<div className="grid grid-cols-2 gap-4">
						<div className="space-y-1">
							<p className="text-xs text-slate-400">
								Monthly Avg
							</p>
							<p className="text-lg font-semibold text-slate-200">
								€{stats.monthlyAverage.toLocaleString()}
							</p>
						</div>
						<div className="space-y-1">
							<p className="text-xs text-slate-400">Last Month</p>
							<p className="text-lg font-semibold text-slate-200">
								€{stats.lastMonthSpending.toLocaleString()}
							</p>
						</div>
					</div>

					{/* Alerts */}
					<div className="grid grid-cols-2 gap-3 pt-2">
						<div className="flex items-center gap-2 p-2 bg-blue-900/30 rounded-lg border border-blue-800/50">
							<Calendar className="w-4 h-4 text-blue-400" />
							<div>
								<p className="text-xs text-slate-300">
									Upcoming
								</p>
								<p className="text-sm font-semibold text-white">
									{stats.upcomingPayments}
								</p>
							</div>
						</div>
						<div className="flex items-center gap-2 p-2 bg-red-900/30 rounded-lg border border-red-800/50">
							<AlertCircle className="w-4 h-4 text-red-400" />
							<div>
								<p className="text-xs text-slate-300">
									Overdue
								</p>
								<p className="text-sm font-semibold text-white">
									{stats.overduePayments}
								</p>
							</div>
						</div>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
