"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, Activity } from "lucide-react";
import { motion } from "framer-motion";
import { useState, useEffect } from "react";
import { transactionApi, tokenManager } from "@/lib/api/client";
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
						{entry.name}: €{entry.value?.toLocaleString()}
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
		const fetchSpendingData = async () => {
			try {
				setLoading(true);
				const user = tokenManager.getUser();
				if (!user?.id) {
					setError("User not found");
					return;
				}

				const response = await transactionApi.getTransactions(
					"123",
					{
						page: 1,
						page_size: 1000,
					}
				);

				const transactions = response.data || [];

				// Aggregate by month
				const monthMap: { [key: string]: number } = {};
				const monthNames = [
					"Jan",
					"Feb",
					"Mar",
					"Apr",
					"May",
					"Jun",
					"Jul",
					"Aug",
					"Sep",
					"Oct",
					"Nov",
					"Dec",
				];

				transactions.forEach((transaction: any) => {
					const date = new Date(transaction.date);
					const monthKey = `${date.getFullYear()}-${date.getMonth()}`;
					const amount = parseFloat(transaction.total_amount || 0);
					monthMap[monthKey] = (monthMap[monthKey] || 0) + amount;
				});

				// Get last 12 months
				const now = new Date();
				const aggregatedData = [];
				for (let i = 11; i >= 0; i--) {
					const targetDate = new Date(
						now.getFullYear(),
						now.getMonth() - i,
						1
					);
					const monthKey = `${targetDate.getFullYear()}-${targetDate.getMonth()}`;
					const spending = monthMap[monthKey] || 0;

					// Simple forecast: 5% increase over average
					const avgSpending =
						Object.values(monthMap).reduce((a, b) => a + b, 0) /
							Object.keys(monthMap).length || 0;
					const forecast = avgSpending * 1.05;

					aggregatedData.push({
						month: monthNames[targetDate.getMonth()],
						spending: spending > 0 ? spending : null,
						forecast: forecast,
						budget: avgSpending * 1.1, // Budget at 10% above average
					});
				}

				setSpendingData(aggregatedData);
				setError(null);
			} catch (err: any) {
				console.error("Failed to fetch spending data:", err);
				setError(err.message || "Failed to load data");
			} finally {
				setLoading(false);
			}
		};

		fetchSpendingData();
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
										`€${value / 1000}k`
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
					<div className="mt-4 p-3 bg-indigo-50 rounded-lg border border-indigo-200">
						<div className="flex items-center gap-2">
							<TrendingUp className="w-4 h-4 text-indigo-600" />
							<p className="text-sm text-gray-700">
								<span className="font-semibold">
									AI Insight:
								</span>{" "}
								Based on your transaction history, spending
								patterns are being analyzed for trends.
							</p>
						</div>
					</div>
				</CardContent>
			</Card>
		</motion.div>
	);
}
