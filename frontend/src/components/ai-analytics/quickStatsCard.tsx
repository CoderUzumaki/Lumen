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
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchDashboard = async () => {
			try {
				setError(null);
				const response = await aiAnalyticsApi.getDashboard();
				if (response.success) {
					setStats(response.data);
				} else {
					setError("Could not load dashboard stats.");
				}
			} catch (err) {
				console.error("Failed to fetch dashboard:", err);
				setError("Could not load dashboard stats.");
			} finally {
				setIsLoading(false);
			}
		};

		fetchDashboard();
	}, []);

	if (isLoading) {
		return (
			<motion.div
				variants={cardVariants}
				initial="hidden"
				animate="visible"
			>
				<Card className="border-border/70 bg-card/80 shadow-lg shadow-black/10">
					<CardHeader className="pb-3">
						<CardTitle className="flex items-center gap-2 text-lg font-semibold text-foreground">
							<DollarSign className="h-5 w-5 text-primary" />
							Quick Stats
						</CardTitle>
					</CardHeader>
					<CardContent>
						<div className="animate-pulse space-y-4">
							<div className="h-8 rounded bg-muted"></div>
							<div className="h-4 w-3/4 rounded bg-muted"></div>
							<div className="h-4 w-1/2 rounded bg-muted"></div>
						</div>
					</CardContent>
				</Card>
			</motion.div>
		);
	}

	if (error || !stats) {
		return (
			<motion.div variants={cardVariants} initial="hidden" animate="visible">
				<Card className="border-border/70 bg-card/80 shadow-lg shadow-black/10">
					<CardHeader className="pb-3">
						<CardTitle className="flex items-center gap-2 text-lg font-semibold text-foreground">
							<AlertCircle className="h-5 w-5 text-amber-300" />
							Quick Stats
						</CardTitle>
					</CardHeader>
					<CardContent>
						<p className="text-sm text-muted-foreground">
							{error || "No analytics data yet. Upload invoices to get started."}
						</p>
					</CardContent>
				</Card>
			</motion.div>
		);
	}

	return (
		<motion.div variants={cardVariants} initial="hidden" animate="visible">
			<Card className="border-border/70 bg-card/80 shadow-lg shadow-black/10 transition-all duration-300 hover:shadow-xl hover:shadow-black/10">
				<CardHeader className="pb-3">
					<CardTitle className="flex items-center gap-2 text-lg font-semibold text-foreground">
						<DollarSign className="h-5 w-5 text-primary" />
						Quick Stats
					</CardTitle>
				</CardHeader>
				<CardContent className="space-y-4">
					{/* Risk Score & Health Status */}
					<div className="space-y-1">
						<p className="text-sm text-muted-foreground">
							Financial Health
						</p>
						<p className="text-3xl font-bold text-foreground">
							{stats.health_status || "HEALTHY"}
						</p>
						<div className="flex items-center gap-1 text-xs">
							<span
								className={`font-medium ${
									stats.risk_level === "LOW"
										? "text-primary"
										: stats.risk_level === "MEDIUM"
										? "text-amber-300"
										: "text-rose-300"
								}`}
							>
								Risk: {stats.risk_level || "LOW"}
							</span>
							<span className="text-muted-foreground">
								Score: {stats.risk_score || 0}/100
							</span>
						</div>
					</div>

					{/* Divider */}
					<div className="border-t border-border/70"></div>

					{/* Quick Metrics Grid */}
					<div className="grid grid-cols-2 gap-4">
						<div className="space-y-1">
							<p className="text-xs text-muted-foreground">
								Patterns Detected
							</p>
							<p className="text-lg font-semibold text-foreground">
								{stats.patterns_detected || 0}
							</p>
						</div>
						<div className="space-y-1">
							<p className="text-xs text-muted-foreground">
								High Risk Anomalies
							</p>
							<p className="text-lg font-semibold text-foreground">
								{stats.high_risk_anomalies || 0}
							</p>
						</div>
					</div>

					{/* Alerts */}
					<div className="grid grid-cols-2 gap-3 pt-2">
						<div className="flex items-center gap-2 rounded-xl border border-primary/20 bg-primary/10 p-2">
							<Calendar className="h-4 w-4 text-primary" />
							<div>
								<p className="text-xs text-muted-foreground">
									Reminders
								</p>
								<p className="text-sm font-semibold text-foreground">
									{stats.active_reminders || 0}
								</p>
							</div>
						</div>
						<div className="flex items-center gap-2 rounded-xl border border-amber-500/20 bg-amber-500/10 p-2">
							<AlertCircle className="h-4 w-4 text-amber-300" />
							<div>
								<p className="text-xs text-muted-foreground">
									Recommendations
								</p>
								<p className="text-sm font-semibold text-foreground">
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
