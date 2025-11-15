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
			<div className="bg-white p-3 border border-gray-200 rounded-lg shadow-lg">
				<p className="font-semibold text-gray-900 mb-2">{label}</p>
				{payload.map((entry: any, index: number) => (
					<p
						key={index}
						className="text-sm font-medium"
						style={{ color: entry.color }}
					>
						{entry.name}: ${entry.value?.toLocaleString()}
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
				const response = await analyticsApi.getAllTimeSummary("123");
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
			<Card className="bg-white border border-gray-200 shadow-sm h-full">
				<CardContent className="flex items-center justify-center h-[400px]">
					<p className="text-gray-500">Loading spending trends...</p>
				</CardContent>
			</Card>
		);
	}

	if (error) {
		return (
			<Card className="bg-white border border-gray-200 shadow-sm h-full">
				<CardContent className="flex items-center justify-center h-[400px]">
					<p className="text-red-500">{error}</p>
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
			<Card className="bg-white border border-gray-200 shadow-sm hover:shadow-md transition-all duration-300 h-full">
				<CardHeader className="pb-3">
					<CardTitle className="text-lg font-semibold text-gray-900 flex items-center justify-between">
						<div className="flex items-center gap-2">
							<Activity className="w-5 h-5 text-indigo-600" />
							Spending Trends
						</div>
						<div className="flex items-center gap-2 text-sm">
							<div className="flex items-center gap-1">
								<div className="w-3 h-3 bg-indigo-400 rounded-full"></div>
								<span className="text-xs text-gray-700">
									Actual
								</span>
							</div>
							<div className="flex items-center gap-1">
								<div className="w-3 h-3 bg-orange-500 rounded-full"></div>
								<span className="text-xs text-gray-700">
									Forecast
								</span>
							</div>
							<div className="flex items-center gap-1">
								<div className="w-3 h-3 bg-gray-500 rounded-full"></div>
								<span className="text-xs text-gray-700">
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
									stroke="#e5e7eb"
								/>
								<XAxis
									dataKey="month"
									stroke="#6b7280"
									style={{ fontSize: "12px" }}
								/>
								<YAxis
									stroke="#6b7280"
									style={{ fontSize: "12px" }}
									tickFormatter={(value) =>
										`₹${value / 1000}k`
									}
								/>
								<Tooltip content={<CustomTooltip />} />
								<Line
									type="monotone"
									dataKey="spending"
									stroke="#818cf8"
									strokeWidth={3}
									dot={{ fill: "#818cf8", r: 4 }}
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
						<h4 className="text-sm font-semibold text-gray-900">
							AI Insights
						</h4>
						<div className="p-3 bg-red-50 rounded-lg border border-red-200">
							<div className="flex items-start gap-2">
								<TrendingUp className="w-4 h-4 text-red-600 mt-0.5" />
								<div>
									<p className="text-sm font-semibold text-red-700">
										November Spending Anomaly Detected
									</p>
									<p className="text-xs text-gray-700 mt-1">
										Your November spending of $8,316 is 454%
										above your monthly average of $1,500.
										This represents an unusual spike with 37
										transactions (48% more than usual).
									</p>
								</div>
							</div>
						</div>
						<div className="p-3 bg-blue-50 rounded-lg border border-blue-200">
							<div className="flex items-start gap-2">
								<TrendingUp className="w-4 h-4 text-blue-600 mt-0.5" />
								<div>
									<p className="text-sm font-semibold text-blue-700">
										Seasonal Pattern Recognition
									</p>
									<p className="text-xs text-gray-700 mt-1">
										Historical data shows spending increases
										in Q3 (Aug-Oct). Your 2024 Q3 averaged
										$1,973/month. Plan for similar patterns
										in 2026.
									</p>
								</div>
							</div>
						</div>
						<div className="p-3 bg-green-50 rounded-lg border border-green-200">
							<div className="flex items-start gap-2">
								<TrendingUp className="w-4 h-4 text-green-600 mt-0.5" />
								<div>
									<p className="text-sm font-semibold text-green-700">
										Spending Discipline Observed
									</p>
									<p className="text-xs text-gray-700 mt-1">
										April-July 2025 maintained excellent
										spending control, averaging just
										$645/month. This shows strong budget
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
