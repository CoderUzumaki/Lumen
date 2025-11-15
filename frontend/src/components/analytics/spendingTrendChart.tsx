"use client";

import {
	Area,
	AreaChart,
	CartesianGrid,
	Tooltip,
	XAxis,
	YAxis,
	ResponsiveContainer,
	Legend,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3 } from "lucide-react";
import { useEffect, useState } from "react";
import { analyticsApi, tokenManager } from "@/lib/api/client";

interface SelectedPeriod {
	year: number;
	month?: number;
	week?: number;
}

interface SpendingTrendChartProps {
	timeRange: "weekly" | "monthly" | "yearly";
	selectedPeriod: SelectedPeriod;
}

interface ChartDataPoint {
	date: string;
	currentSpending: number;
	previousSpending: number;
	transactions: number;
}

const getPeriodLabels = (timeRange: string, selectedPeriod: SelectedPeriod) => {
	if (timeRange === "yearly") {
		return {
			current: `${selectedPeriod.year}`,
			previous: `${selectedPeriod.year - 1}`,
		};
	} else if (timeRange === "monthly" && selectedPeriod.month !== undefined) {
		const months = [
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
		const prevMonth =
			selectedPeriod.month === 0 ? 11 : selectedPeriod.month - 1;
		const prevYear =
			selectedPeriod.month === 0
				? selectedPeriod.year - 1
				: selectedPeriod.year;
		return {
			current: `${months[selectedPeriod.month]} ${selectedPeriod.year}`,
			previous: `${months[prevMonth]} ${prevYear}`,
		};
	} else if (timeRange === "weekly" && selectedPeriod.week) {
		const prevWeek =
			selectedPeriod.week === 1 ? 52 : selectedPeriod.week - 1;
		const prevYear =
			selectedPeriod.week === 1
				? selectedPeriod.year - 1
				: selectedPeriod.year;
		return {
			current: `Week ${selectedPeriod.week}, ${selectedPeriod.year}`,
			previous: `Week ${prevWeek}, ${prevYear}`,
		};
	}
	return { current: "Current Period", previous: "Previous Period" };
};

const CustomTooltip = ({ active, payload, label }: any) => {
	if (active && payload && payload.length) {
		return (
			<div className="bg-white p-4 rounded-lg shadow-lg border border-gray-200">
				<p className="font-semibold text-sm mb-2 text-gray-900">
					{label}
				</p>
				{payload.map((entry: any, index: number) => (
					<p
						key={index}
						className="text-xs font-medium"
						style={{ color: entry.color }}
					>
						{entry.name === "currentSpending"
							? "Current Period"
							: "Previous Period"}
						: $
						{entry.value.toLocaleString("en-US", {
							minimumFractionDigits: 2,
							maximumFractionDigits: 2,
						})}
					</p>
				))}
			</div>
		);
	}
	return null;
};

export default function SpendingTrendChart({
	timeRange,
	selectedPeriod,
}: SpendingTrendChartProps) {
	const [chartData, setChartData] = useState<ChartDataPoint[]>([]);
	const [loading, setLoading] = useState(true);

	useEffect(() => {
		const fetchChartData = async () => {
			try {
				setLoading(true);
				const user = tokenManager.getUser();
				// if (!user?.id) return;

				const response = await analyticsApi.getTimeRangeAnalytics(
					"123",
					timeRange,
					selectedPeriod.year,
					selectedPeriod.month,
					selectedPeriod.week
				);

				if (response.success && response.chart_data) {
					setChartData(response.chart_data);
				}
			} catch (error) {
				console.error("Error fetching chart data:", error);
			} finally {
				setLoading(false);
			}
		};

		fetchChartData();
	}, [timeRange, selectedPeriod]);

	const periodLabels = getPeriodLabels(timeRange, selectedPeriod);

	if (loading) {
		return (
			<Card className="col-span-full bg-white border border-gray-200">
				<CardHeader>
					<div className="h-6 w-48 bg-gray-200 rounded animate-pulse"></div>
				</CardHeader>
				<CardContent>
					<div className="h-[400px] w-full bg-gray-200 rounded animate-pulse"></div>
				</CardContent>
			</Card>
		);
	}

	return (
		<Card className="w-full bg-white border border-gray-200 shadow-sm">
			<CardHeader>
				<CardTitle className="flex items-center gap-2 text-gray-900">
					<BarChart3 className="w-5 h-5 text-primary" />
					Spending Comparison
				</CardTitle>
				<p className="text-sm text-gray-600">
					Comparing{" "}
					<span className="font-semibold text-primary">
						{periodLabels.current}
					</span>{" "}
					vs{" "}
					<span className="font-semibold text-gray-700">
						{periodLabels.previous}
					</span>
				</p>
			</CardHeader>
			<CardContent>
				<ResponsiveContainer width="100%" height={400}>
					<AreaChart
						data={chartData}
						margin={{ top: 10, right: 30, left: 0, bottom: 0 }}
					>
						<defs>
							<linearGradient
								id="colorSpending"
								x1="0"
								y1="0"
								x2="0"
								y2="1"
							>
								<stop
									offset="5%"
									stopColor="#8884d8"
									stopOpacity={0.8}
								/>
								<stop
									offset="95%"
									stopColor="#8884d8"
									stopOpacity={0}
								/>
							</linearGradient>
							<linearGradient
								id="colorIncome"
								x1="0"
								y1="0"
								x2="0"
								y2="1"
							>
								<stop
									offset="5%"
									stopColor="#82ca9d"
									stopOpacity={0.8}
								/>
								<stop
									offset="95%"
									stopColor="#82ca9d"
									stopOpacity={0}
								/>
							</linearGradient>
						</defs>
						<CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
						<XAxis
							dataKey="date"
							tick={{ fontSize: 12 }}
							tickLine={false}
						/>
						<YAxis
							tick={{ fontSize: 12 }}
							tickLine={false}
							tickFormatter={(value) => `$${value}`}
						/>
						<Tooltip content={<CustomTooltip />} />
						<Legend
							wrapperStyle={{ paddingTop: "20px" }}
							iconType="circle"
						/>
						<Area
							type="monotone"
							dataKey="currentSpending"
							stroke="#8884d8"
							fillOpacity={1}
							fill="url(#colorSpending)"
							strokeWidth={2}
							name="currentSpending"
							animationDuration={1000}
						/>
						<Area
							type="monotone"
							dataKey="previousSpending"
							stroke="#82ca9d"
							fillOpacity={1}
							fill="url(#colorIncome)"
							strokeWidth={2}
							name="previousSpending"
							animationDuration={1000}
						/>
					</AreaChart>
				</ResponsiveContainer>
			</CardContent>
		</Card>
	);
}
