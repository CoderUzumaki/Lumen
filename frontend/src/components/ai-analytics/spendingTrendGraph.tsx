"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, Activity } from "lucide-react";
import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import { analyticsApi } from "@/lib/api/client";
import {
	LineChart,
	Line,
	XAxis,
	YAxis,
	CartesianGrid,
	Tooltip,
	ResponsiveContainer,
	Legend,
} from "recharts";

const cardVariants = {
	hidden: { opacity: 0, y: 20 },
	visible: {
		opacity: 1,
		y: 0,
		transition: {
			duration: 0.5,
			ease: [0.4, 0, 0.2, 1] as any,
			delay: 0.5,
		},
	},
};

const CustomTooltip = ({ active, payload, label }: any) => {
	if (active && payload && payload.length) {
		return (
			<div className="rounded-xl border border-border/70 bg-card/95 p-3 shadow-xl shadow-black/20">
				<p className="mb-2 font-semibold text-foreground">{label}</p>
				{payload.map((entry: any, index: number) => (
					<p
						key={index}
						className="text-sm font-medium"
						style={{ color: entry.color }}
					>
						{entry.name}: ₹{entry.value?.toLocaleString()}
					</p>
				))}
			</div>
		);
	}
	return null;
};

export default function SpendingTrendGraph() {
	const [spendingData, setSpendingData] = useState<any[]>([]);
	const [loading, setLoading] = useState(true);
	const [error, setError] = useState<string | null>(null);

	useEffect(() => {
		const fetchSpendingTrends = async () => {
			try {
				const response = await analyticsApi.getAllTimeSummary();
				if (response.success && response.monthly_trends) {
					setSpendingData(response.monthly_trends);
				} else {
					setSpendingData([]);
				}
			} catch (err) {
				setError("Failed to load spending trends");
				setSpendingData([]);
			} finally {
				setLoading(false);
			}
		};
		fetchSpendingTrends();
	}, []);

	if (loading) {
		return (
			<Card className="h-full border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardContent className="flex items-center justify-center h-[400px]">
					<p className="text-muted-foreground">Loading spending trends...</p>
				</CardContent>
			</Card>
		);
	}

	if (error) {
		return (
			<Card className="h-full border-border/70 bg-card/80 shadow-lg shadow-black/10">
				<CardContent className="flex items-center justify-center h-[400px]">
					<p className="text-rose-300">{error}</p>
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
			<Card className="h-full border-border/70 bg-card/80 shadow-lg shadow-black/10 transition-all duration-300 hover:shadow-xl hover:shadow-black/10">
				<CardHeader className="pb-3">
					<CardTitle className="flex items-center justify-between text-lg font-semibold text-foreground">
						<div className="flex items-center gap-2">
							<Activity className="h-5 w-5 text-primary" />
							Spending Trends
						</div>
						<div className="flex items-center gap-2 text-sm">
							<div className="flex items-center gap-1">
								<div className="h-3 w-3 rounded-full bg-primary"></div>
								<span className="text-xs text-muted-foreground">
									Actual
								</span>
							</div>
							<div className="flex items-center gap-1">
								<div className="h-3 w-3 rounded-full bg-amber-500"></div>
								<span className="text-xs text-muted-foreground">
									Forecast
								</span>
							</div>
							<div className="flex items-center gap-1">
								<div className="h-3 w-3 rounded-full bg-slate-400"></div>
								<span className="text-xs text-muted-foreground">
									Budget
								</span>
							</div>
						</div>
					</CardTitle>
				</CardHeader>
				<CardContent>
					<div className="h-[300px] w-full">
						<ResponsiveContainer width="100%" height="100%">
							<LineChart
								data={spendingData}
								margin={{
									top: 5,
									right: 20,
									left: 10,
									bottom: 5,
								}}
							>
								<CartesianGrid
									strokeDasharray="3 3"
									stroke="rgba(148, 163, 184, 0.18)"
								/>
								<XAxis
									dataKey="month"
									stroke="#94a3b8"
									style={{ fontSize: "12px" }}
								/>
								<YAxis
									stroke="#94a3b8"
									style={{ fontSize: "12px" }}
									tickFormatter={(value) =>
										`₹${value / 1000}k`
									}
								/>
								<Tooltip content={<CustomTooltip />} />
								<Line
									type="monotone"
									dataKey="spending"
									stroke="#60a5fa"
									strokeWidth={3}
									dot={{ fill: "#60a5fa", r: 4 }}
									activeDot={{ r: 6 }}
									name="Actual Spending"
								/>
								<Line
									type="monotone"
									dataKey="forecast"
									stroke="#f97316"
									strokeWidth={2}
									strokeDasharray="5 5"
									dot={{ fill: "#f97316", r: 3 }}
									name="AI Forecast"
								/>
								<Line
									type="monotone"
									dataKey="budget"
									stroke="#64748b"
									strokeWidth={2}
									strokeDasharray="3 3"
									dot={false}
									name="Budget"
								/>
							</LineChart>
						</ResponsiveContainer>
					</div>
					<div className="mt-4 space-y-3">
						<h4 className="text-sm font-semibold text-foreground">
							AI Insights
						</h4>
						<div className="rounded-xl border border-rose-400/20 bg-rose-500/10 p-3">
							<div className="flex items-start gap-2">
								<TrendingUp className="mt-0.5 h-4 w-4 text-rose-300" />
								<div>
									<p className="text-sm font-semibold text-rose-300">
										November Spending Anomaly Detected
									</p>
									<p className="mt-1 text-xs text-muted-foreground">
										Your November spending of ₹8,316 is 454%
										above your monthly average of ₹1,500.
										This represents an unusual spike with 37
										transactions (48% more than usual).
									</p>
								</div>
							</div>
						</div>
						<div className="rounded-xl border border-primary/20 bg-primary/10 p-3">
							<div className="flex items-start gap-2">
								<TrendingUp className="mt-0.5 h-4 w-4 text-primary" />
								<div>
									<p className="text-sm font-semibold text-primary">
										Seasonal Pattern Recognition
									</p>
									<p className="mt-1 text-xs text-muted-foreground">
										Historical data shows spending increases
										in Q3 (Aug-Oct). Your 2024 Q3 averaged
										₹1,973/month. Plan for similar patterns
										in 2026.
									</p>
								</div>
							</div>
						</div>
						<div className="rounded-xl border border-emerald-400/20 bg-emerald-500/10 p-3">
							<div className="flex items-start gap-2">
								<TrendingUp className="mt-0.5 h-4 w-4 text-emerald-300" />
								<div>
									<p className="text-sm font-semibold text-emerald-300">
										Spending Discipline Observed
									</p>
									<p className="mt-1 text-xs text-muted-foreground">
										April-July 2025 maintained excellent
										spending control, averaging just
										₹645/month. This shows strong budget
										adherence during low-activity periods.
									</p>
								</div>
							</div>
						</div>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
