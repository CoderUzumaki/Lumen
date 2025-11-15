"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, DollarSign, Calendar, AlertCircle } from "lucide-react";
import { motion } from "framer-motion";
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
		},
	},
};

export default function QuickStatsCard() {
	const [stats, setStats] = useState<any>(null);
	const [isLoading, setIsLoading] = useState(true);

	useEffect(() => {
		const fetchDashboard = async () => {
			try {
				const response = await aiAnalyticsApi.getDashboard("123");
				if (response.success) {
					setStats(response.data);
				}
			} catch (error) {
				console.error("Failed to fetch dashboard:", error);
			} finally {
				setIsLoading(false);
			}
		};

		fetchDashboard();
	}, []);

	if (isLoading || !stats) {
		return (
			<motion.div
				variants={cardVariants}
				initial="hidden"
				animate="visible"
			>
				<Card className="bg-white border border-gray-200 shadow-sm">
					<CardHeader className="pb-3">
						<CardTitle className="text-lg font-semibold text-gray-900 flex items-center gap-2">
							<DollarSign className="w-5 h-5 text-blue-600" />
							Quick Stats
						</CardTitle>
					</CardHeader>
					<CardContent>
						<div className="animate-pulse space-y-4">
							<div className="h-8 bg-gray-200 rounded"></div>
							<div className="h-4 bg-gray-200 rounded w-3/4"></div>
							<div className="h-4 bg-gray-200 rounded w-1/2"></div>
						</div>
					</CardContent>
				</Card>
			</motion.div>
		);
	}

	return (
		<motion.div variants={cardVariants} initial="hidden" animate="visible">
			<Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-all duration-300">
				<CardHeader className="pb-3">
					<CardTitle className="text-lg font-semibold text-gray-900 flex items-center gap-2">
						<DollarSign className="w-5 h-5 text-blue-600" />
						Quick Stats
					</CardTitle>
				</CardHeader>
				<CardContent className="space-y-4">
					{/* Risk Score & Health Status */}
					<div className="space-y-1">
						<p className="text-sm text-gray-600">
							Financial Health
						</p>
						<p className="text-3xl font-bold text-gray-900">
							{stats.health_status || "HEALTHY"}
						</p>
						<div className="flex items-center gap-1 text-xs">
							<span
								className={`font-medium ${
									stats.risk_level === "LOW"
										? "text-blue-600"
										: stats.risk_level === "MEDIUM"
										? "text-yellow-600"
										: "text-red-600"
								}`}
							>
								Risk: {stats.risk_level || "LOW"}
							</span>
							<span className="text-gray-500">
								Score: {stats.risk_score || 0}/100
							</span>
						</div>
					</div>

					{/* Divider */}
					<div className="border-t border-gray-200"></div>

					{/* Quick Metrics Grid */}
					<div className="grid grid-cols-2 gap-4">
						<div className="space-y-1">
							<p className="text-xs text-gray-600">
								Patterns Detected
							</p>
							<p className="text-lg font-semibold text-gray-900">
								{stats.patterns_detected || 0}
							</p>
						</div>
						<div className="space-y-1">
							<p className="text-xs text-gray-600">
								High Risk Anomalies
							</p>
							<p className="text-lg font-semibold text-gray-900">
								{stats.high_risk_anomalies || 0}
							</p>
						</div>
					</div>

					{/* Alerts */}
					<div className="grid grid-cols-2 gap-3 pt-2">
						<div className="flex items-center gap-2 p-2 bg-blue-50 rounded-lg border border-blue-200">
							<Calendar className="w-4 h-4 text-blue-600" />
							<div>
								<p className="text-xs text-gray-600">
									Reminders
								</p>
								<p className="text-sm font-semibold text-gray-900">
									{stats.active_reminders || 0}
								</p>
							</div>
						</div>
						<div className="flex items-center gap-2 p-2 bg-amber-50 rounded-lg border border-amber-200">
							<AlertCircle className="w-4 h-4 text-amber-600" />
							<div>
								<p className="text-xs text-gray-600">
									Recommendations
								</p>
								<p className="text-sm font-semibold text-gray-900">
									{stats.top_recommendations?.length || 0}
								</p>
							</div>
						</div>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
